"""FastAPI dependency injection: DB sessions, config, auth."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException

from hermas.config import AppConfig, get_config
from hermas.database import get_session_factory
from hermas.services import session_service

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
    x_session_token: str = Header("", alias="X-Session-Token"),
    x_user_id: str = Header("", alias="X-User-Id"),
) -> str:
    """Returns the authenticated user_id."""
    if not cfg.require_auth:
        return x_user_id.strip() if x_user_id.strip() else "anonymous"

    if not x_session_token.strip():
        raise HTTPException(401, detail="Missing X-Session-Token")

    user_id = await session_service.validate_session(db, x_session_token)
    if user_id is None:
        raise HTTPException(401, detail="Session expired or invalid")
    return user_id
