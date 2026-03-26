"""Tests for database initialization."""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_tables_exist(db_session: AsyncSession):
    """Verify that all expected tables are created."""
    result = await db_session.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
    tables = {row[0] for row in result}
    assert "conversations" in tables
    assert "messages" in tables
    assert "sessions" in tables
    assert "skills" in tables
    assert "mcp_servers" in tables


@pytest.mark.asyncio
async def test_fts_table_exists(db_session: AsyncSession):
    """Verify the FTS5 virtual table is created."""
    result = await db_session.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
    tables = {row[0] for row in result}
    assert "messages_fts" in tables


@pytest.mark.asyncio
async def test_insert_and_query(db_session: AsyncSession):
    """Verify basic insert/query works."""
    from solomon.models.skill import Skill

    skill = Skill(id="test-1", user_id="__global__", name="Test", description="Test skill", content="Do stuff")
    db_session.add(skill)
    await db_session.commit()

    result = await db_session.execute(text("SELECT name FROM skills WHERE id = 'test-1'"))
    row = result.first()
    assert row is not None
    assert row[0] == "Test"
