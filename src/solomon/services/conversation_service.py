"""Conversation persistence service using SQLAlchemy async."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from solomon.models.conversation import Conversation, Message


def _safe_user_id(user_id: str) -> str:
    cleaned = re.sub(r"[^a-z0-9_-]+", "-", user_id.strip().lower())
    return cleaned or "anonymous"


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def _title_from_messages(messages: list[dict]) -> str:
    for msg in messages:
        if msg.get("role") == "user":
            content = str(msg.get("content", "")).strip()
            if content:
                return content[:64] + "..." if len(content) > 64 else content
    return "Conversation"


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


async def list_conversations(db: AsyncSession, user_id: str) -> list[dict]:
    safe_user = _safe_user_id(user_id)
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == safe_user)
        .order_by(Conversation.updated_at.desc())
    )
    return [
        {
            "id": c.id,
            "title": c.title,
            "updatedAt": _iso(c.updated_at),
            "model": c.model,
        }
        for c in result.scalars()
    ]


async def load_conversation(db: AsyncSession, user_id: str, conversation_id: str) -> dict | None:
    safe_user = _safe_user_id(user_id)
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == safe_user)
    )
    conv = result.scalar_one_or_none()
    if conv is None:
        return None
    return {
        "id": conv.id,
        "title": conv.title,
        "model": conv.model,
        "createdAt": _iso(conv.created_at),
        "updatedAt": _iso(conv.updated_at),
        "messages": [{"role": m.role, "content": m.content} for m in conv.messages],
    }


async def save_conversation(
    db: AsyncSession,
    user_id: str,
    conversation_id: str,
    model: str,
    messages: list[dict],
) -> dict:
    safe_user = _safe_user_id(user_id)
    now = datetime.now(UTC)
    title = _title_from_messages(messages)

    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    conv = result.scalar_one_or_none()

    if conv is None:
        conv = Conversation(
            id=conversation_id,
            user_id=safe_user,
            title=title,
            model=model,
            created_at=now,
            updated_at=now,
        )
        db.add(conv)
    else:
        conv.user_id = safe_user
        conv.title = title
        conv.model = model
        conv.updated_at = now

    # Replace all messages
    await db.execute(delete(Message).where(Message.conversation_id == conversation_id))
    for idx, msg in enumerate(messages):
        db.add(
            Message(
                conversation_id=conversation_id,
                idx=idx,
                role=str(msg.get("role", "assistant")),
                content=str(msg.get("content", "")),
            )
        )

    # Update FTS index
    await db.execute(text("DELETE FROM messages_fts WHERE conversation_id = :cid"), {"cid": conversation_id})
    for msg in messages:
        content = str(msg.get("content", ""))
        if content.strip():
            await db.execute(
                text("INSERT INTO messages_fts (conversation_id, content) VALUES (:cid, :content)"),
                {"cid": conversation_id, "content": content},
            )

    await db.commit()
    await db.refresh(conv)

    return {
        "id": conv.id,
        "title": conv.title,
        "model": conv.model,
        "createdAt": _iso(conv.created_at),
        "updatedAt": _iso(conv.updated_at),
        "messages": messages,
    }


async def search_conversations(db: AsyncSession, user_id: str, query: str) -> list[dict]:
    safe_user = _safe_user_id(user_id)
    needle = query.strip()
    if not needle:
        return []

    # Use FTS5 to find matching conversation IDs
    fts_result = await db.execute(
        text(
            """
            SELECT DISTINCT f.conversation_id, snippet(messages_fts, 1, '<mark>', '</mark>', '...', 32) AS excerpt
            FROM messages_fts f
            JOIN conversations c ON c.id = f.conversation_id
            WHERE c.user_id = :user_id AND messages_fts MATCH :query
            ORDER BY rank
            LIMIT 50
            """
        ),
        {"user_id": safe_user, "query": needle},
    )
    fts_rows = fts_result.fetchall()
    if not fts_rows:
        return []

    conv_ids = [row[0] for row in fts_rows]
    excerpts = {row[0]: row[1] for row in fts_rows}

    result = await db.execute(
        select(Conversation)
        .where(Conversation.id.in_(conv_ids), Conversation.user_id == safe_user)
        .order_by(Conversation.updated_at.desc())
    )

    return [
        {
            "id": c.id,
            "title": c.title,
            "updatedAt": _iso(c.updated_at),
            "excerpt": excerpts.get(c.id, ""),
        }
        for c in result.scalars()
    ]
