"""Async SQLAlchemy engine and session factory for SQLite."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from hermas.config import AppConfig

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _db_url(cfg: AppConfig) -> str:
    data_dir = Path(cfg.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / "hermas.db"
    return f"sqlite+aiosqlite:///{db_path}"


async def init_engine(cfg: AppConfig) -> None:
    global _engine, _session_factory
    if _engine is not None:
        return
    _engine = create_async_engine(
        _db_url(cfg),
        echo=False,
        connect_args={"check_same_thread": False},
    )
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)

    from hermas.models.base import Base

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Create FTS5 virtual table for full-text message search
        await conn.execute(
            text(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts
                USING fts5(conversation_id, content, tokenize='porter')
                """
            )
        )



async def close_engine() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("Database not initialized. Call init_engine() first.")
    return _session_factory
