"""FastAPI dependency injection: DB sessions, config, auth."""

from __future__ import annotations

import json
import time
from typing import Annotated

import httpx
import jwt
from fastapi import Depends, Header, HTTPException

from hermas.config import AppConfig, get_config
from hermas.database import get_session_factory
from hermas.services import session_service

_JWKS_CACHE: dict[str, tuple[float, dict]] = {}

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def get_app_config() -> AppConfig:
    return get_config()


# ---------------------------------------------------------------------------
# Database session
# ---------------------------------------------------------------------------


async def get_db():
    factory = get_session_factory()
    async with factory() as session:
        yield session


# ---------------------------------------------------------------------------
# Auth dependencies
# ---------------------------------------------------------------------------


async def require_app_token(
    cfg: Annotated[AppConfig, Depends(get_app_config)],
    x_app_token: str = Header("", alias="X-App-Token"),
) -> None:
    if not cfg.require_auth:
        return
    if not cfg.app_api_token.strip():
        raise HTTPException(500, detail="Server auth is enabled but HERMAS_APP_API_TOKEN is missing")
    if x_app_token != cfg.app_api_token:
        raise HTTPException(401, detail="Invalid app token")


async def require_session(
    cfg: Annotated[AppConfig, Depends(get_app_config)],
    db=Depends(get_db),
    authorization: str = Header("", alias="Authorization"),
    x_session_token: str = Header("", alias="X-Session-Token"),
    x_user_id: str = Header("", alias="X-User-Id"),
) -> str:
    """Returns the authenticated user_id."""
    if not cfg.require_auth:
        return x_user_id.strip() if x_user_id.strip() else "anonymous"

    provider = cfg.auth_provider.strip().lower()
    if provider == "auth0":
        return await _require_auth0_user(cfg, authorization)
    if provider != "session":
        raise HTTPException(500, detail=f"Unsupported auth provider: {cfg.auth_provider}")

    if not x_session_token.strip():
        raise HTTPException(401, detail="Missing X-Session-Token")

    user_id = await session_service.validate_session(db, x_session_token)
    if user_id is None:
        raise HTTPException(401, detail="Session expired or invalid")
    return user_id


def _auth0_jwks_url(cfg: AppConfig) -> str:
    issuer = cfg.auth0_issuer.strip().rstrip("/")
    if issuer:
        return f"{issuer}/.well-known/jwks.json"
    domain = cfg.auth0_domain.strip()
    if domain:
        return f"https://{domain}/.well-known/jwks.json"
    raise HTTPException(500, detail="Auth0 is enabled but no issuer/domain is configured")


async def _get_jwks(cfg: AppConfig) -> dict:
    jwks_url = _auth0_jwks_url(cfg)
    now = time.monotonic()
    cached = _JWKS_CACHE.get(jwks_url)
    if cached and cached[0] > now:
        return cached[1]

    timeout = httpx.Timeout(5.0, connect=5.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(jwks_url)
        resp.raise_for_status()
        payload = resp.json()
    if not isinstance(payload, dict) or not isinstance(payload.get("keys"), list):
        raise HTTPException(500, detail="Invalid JWKS response from Auth0")

    ttl = max(int(cfg.auth0_jwks_cache_ttl_seconds), 60)
    _JWKS_CACHE[jwks_url] = (now + ttl, payload)
    return payload


def _get_bearer_token(authorization: str) -> str:
    raw = authorization.strip()
    if not raw:
        raise HTTPException(401, detail="Missing Authorization header")
    prefix = "bearer "
    if not raw.lower().startswith(prefix):
        raise HTTPException(401, detail="Authorization must be Bearer token")
    token = raw[len(prefix):].strip()
    if not token:
        raise HTTPException(401, detail="Bearer token is empty")
    return token


async def _require_auth0_user(cfg: AppConfig, authorization: str) -> str:
    if not cfg.auth0_audience.strip():
        raise HTTPException(500, detail="Auth0 is enabled but HERMAS_AUTH0_AUDIENCE is missing")

    token = _get_bearer_token(authorization)

    try:
        unverified = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise HTTPException(401, detail="Invalid JWT header") from exc

    kid = str(unverified.get("kid", "")).strip()
    if not kid:
        raise HTTPException(401, detail="JWT missing key id")

    jwks = await _get_jwks(cfg)
    key = next((k for k in jwks.get("keys", []) if isinstance(k, dict) and str(k.get("kid", "")) == kid), None)
    if key is None:
        raise HTTPException(401, detail="JWT key not recognized")

    issuer = cfg.auth0_issuer.strip()
    if not issuer:
        domain = cfg.auth0_domain.strip()
        if not domain:
            raise HTTPException(500, detail="Auth0 is enabled but HERMAS_AUTH0_ISSUER/HERMAS_AUTH0_DOMAIN is missing")
        issuer = f"https://{domain}/"

    try:
        public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key))
        claims = jwt.decode(
            token,
            key=public_key,
            algorithms=[cfg.auth0_algorithm],
            audience=cfg.auth0_audience,
            issuer=issuer,
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(401, detail="Token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(401, detail="Invalid token") from exc

    user_id = str(claims.get("sub", "")).strip()
    if not user_id:
        raise HTTPException(401, detail="Token missing subject")
    return user_id
