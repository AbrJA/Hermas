"""Chat endpoints – synchronous and SSE streaming."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from solomon.api.dependencies import get_app_config, get_db, require_session
from solomon.config import AppConfig
from solomon.services import chat_service

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat")
async def chat(
    request: Request,
    cfg: Annotated[AppConfig, Depends(get_app_config)],
    user_id: Annotated[str, Depends(require_session)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    payload = await request.json()
    result = await chat_service.complete_chat(cfg, user_id, payload, db)
    return JSONResponse({
        "conversationId": result["conversationId"],
        "message": {"role": "assistant", "content": result["content"]},
        "model": result["model"],
        "usage": result["usage"],
        "appliedSkillIds": result["appliedSkillIds"],
    })


@router.post("/chat/stream")
async def chat_stream(
    request: Request,
    cfg: Annotated[AppConfig, Depends(get_app_config)],
    user_id: Annotated[str, Depends(require_session)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    payload = await request.json()

    async def event_generator():
        async for event_str in chat_service.complete_chat_stream(cfg, user_id, payload, db):
            yield event_str.encode("utf-8")

    return EventSourceResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-cache",
        },
    )
