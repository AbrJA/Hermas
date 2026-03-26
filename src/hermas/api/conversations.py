"""Conversation endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from hermas.api.dependencies import get_db, require_session
from hermas.services import conversation_service

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.get("/list")
async def list_conversations(
    user_id: Annotated[str, Depends(require_session)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    summaries = await conversation_service.list_conversations(db, user_id)
    return {"userId": user_id, "conversations": summaries}


@router.get("/load")
async def load_conversation(
    user_id: Annotated[str, Depends(require_session)],
    db: Annotated[AsyncSession, Depends(get_db)],
    id: str = Query(..., alias="id"),
):
    entry = await conversation_service.load_conversation(db, user_id, id)
    if entry is None:
        raise HTTPException(404, detail="Conversation not found")
    return {"userId": user_id, "conversation": entry}


@router.get("/search")
async def search_conversations(
    user_id: Annotated[str, Depends(require_session)],
    db: Annotated[AsyncSession, Depends(get_db)],
    q: str = Query(...),
):
    results = await conversation_service.search_conversations(db, user_id, q)
    return {"userId": user_id, "query": q, "results": results}
