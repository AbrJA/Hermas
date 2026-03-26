"""Shared test fixtures."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from solomon.config import AppConfig
from solomon.models.base import Base


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def app_config() -> AppConfig:
    return AppConfig(
        host="127.0.0.1",
        port=8080,
        llm_base_url="https://api.openai.com",
        default_model="gpt-4.1-mini",
        default_api_key="test-key-123",
        system_prompt="You are Solomon, a test assistant.",
        skills_dir="skills",
        data_dir="test_data",
        cors_origin="*",
        request_timeout_seconds=5,
        require_auth=False,
        app_api_token="test-app-token",
        session_ttl_seconds=3600,
    )


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Create FTS5 virtual table
        from sqlalchemy import text
        await conn.execute(text(
            "CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts "
            "USING fts5(conversation_id, content, tokenize='porter')"
        ))
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_engine, app_config, monkeypatch) -> AsyncGenerator[AsyncClient, None]:
    """Test client with in-memory DB and mocked config."""
    from solomon import config as config_mod
    from solomon import database as db_mod
    from solomon.main import create_app

    # Override config
    monkeypatch.setattr(config_mod, "_config", app_config)

    # Override database engine
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    monkeypatch.setattr(db_mod, "_engine", db_engine)
    monkeypatch.setattr(db_mod, "_session_factory", factory)

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
