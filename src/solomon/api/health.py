"""Health / config endpoints."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends

from solomon.api.dependencies import get_app_config
from solomon.config import AppConfig

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health():
    return {"status": "ok", "service": "solomon"}


@router.get("/readiness")
async def readiness(cfg: Annotated[AppConfig, Depends(get_app_config)]):
    skills_ok = Path(cfg.skills_dir).is_dir()
    data_ok = True
    try:
        Path(cfg.data_dir).mkdir(parents=True, exist_ok=True)
    except OSError:
        data_ok = False
    status_code = 200 if (skills_ok and data_ok) else 503
    return {
        "ready": status_code == 200,
        "checks": {"skillsDir": skills_ok, "dataDirWritable": data_ok},
    }


@router.get("/config")
async def config_endpoint(cfg: Annotated[AppConfig, Depends(get_app_config)]):
    return {
        "defaultModel": cfg.default_model,
        "baseUrl": cfg.llm_base_url,
        "hasBackendApiKey": bool(cfg.default_api_key.strip()),
        "requireAuth": cfg.require_auth,
        "requestTimeoutSeconds": cfg.request_timeout_seconds,
    }
