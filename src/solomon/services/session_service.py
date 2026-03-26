"""DB-backed session service replacing in-memory storage."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from solomon.models.session import Session


def _now_unix() -> int:
    return int(datetime.now(UTC).timestamp())


async def cleanup_expired(db: AsyncSession) -> int:
    """Delete expired sessions and return count removed."""
    result = await db.execute(delete(Session).where(Session.expires_at <= _now_unix()))
    await db.commit()
    return result.rowcount  # type: ignore[return-value]


async def create_session(db: AsyncSession, user_id: str, ttl_seconds: int) -> str:
    await cleanup_expired(db)
    token = str(uuid.uuid4())
    expires_at = _now_unix() + max(ttl_seconds, 60)
    db.add(Session(token=token, user_id=user_id, expires_at=expires_at))
    await db.commit()
    return token


async def validate_session(db: AsyncSession, token: str) -> str | None:
    result = await db.execute(select(Session).where(Session.token == token))
    session = result.scalar_one_or_none()
    if session is None:
        return None
    if session.expires_at <= _now_unix():
        await db.delete(session)
        await db.commit()
        return None
    return session.user_id


async def session_expires_at(db: AsyncSession, token: str) -> int | None:
    result = await db.execute(select(Session).where(Session.token == token))
    session = result.scalar_one_or_none()
    return session.expires_at if session else None
