"""Tests for session service."""

import pytest

from hermas.services import session_service


@pytest.mark.asyncio
async def test_create_and_validate_session(db_session):
    token = await session_service.create_session(db_session, "alice", 3600)
    assert isinstance(token, str)
    assert len(token) == 36  # UUID format

    user_id = await session_service.validate_session(db_session, token)
    assert user_id == "alice"


@pytest.mark.asyncio
async def test_validate_nonexistent_session(db_session):
    result = await session_service.validate_session(db_session, "nonexistent-token")
    assert result is None


@pytest.mark.asyncio
async def test_session_expires_at(db_session):
    token = await session_service.create_session(db_session, "bob", 3600)
    expires_at = await session_service.session_expires_at(db_session, token)
    assert expires_at is not None
    assert isinstance(expires_at, int)
    assert expires_at > 0


@pytest.mark.asyncio
async def test_expired_session_returns_none(db_session):
    # Create with minimal TTL (60 seconds minimum enforced), then manipulate
    token = await session_service.create_session(db_session, "charlie", 60)

    # Manually expire it
    from sqlalchemy import update

    from hermas.models.session import Session

    await db_session.execute(
        update(Session).where(Session.token == token).values(expires_at=0)
    )
    await db_session.commit()

    result = await session_service.validate_session(db_session, token)
    assert result is None


@pytest.mark.asyncio
async def test_cleanup_expired(db_session):
    # Create a session and expire it
    token = await session_service.create_session(db_session, "dave", 60)
    from sqlalchemy import update

    from hermas.models.session import Session

    await db_session.execute(
        update(Session).where(Session.token == token).values(expires_at=0)
    )
    await db_session.commit()

    count = await session_service.cleanup_expired(db_session)
    assert count >= 1
