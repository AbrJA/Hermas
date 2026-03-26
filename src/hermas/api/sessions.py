"""Session endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from hermas.api.dependencies import get_app_config, get_db, require_app_token
from hermas.config import AppConfig
from hermas.schemas.session import SessionCreateRequest, SessionCreateResponse
from hermas.services import session_service

router = APIRouter(prefix="/api", tags=["sessions"])


@router.post("/session", response_model=SessionCreateResponse)
async def create_session(
    body: SessionCreateRequest,
    cfg: Annotated[AppConfig, Depends(get_app_config)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[None, Depends(require_app_token)],
):
    user_id = body.userId.strip() if body.userId.strip() else f"user-{uuid.uuid4()}"
    token = await session_service.create_session(db, user_id, cfg.session_ttl_seconds)
    expires_at = await session_service.session_expires_at(db, token)
    return SessionCreateResponse(sessionToken=token, userId=user_id, expiresAt=expires_at or 0)
