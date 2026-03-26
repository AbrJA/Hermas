"""FastAPI application factory and entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

import structlog
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from solomon.config import AppConfig, get_config
from solomon.database import close_engine, get_session_factory, init_engine

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = get_config()
    logger.info("starting", host=cfg.host, port=cfg.port, data_dir=cfg.data_dir)

    # Initialize DB
    await init_engine(cfg)

    # Seed skills from filesystem on first boot
    factory = get_session_factory()
    async with factory() as db:
        from solomon.services import skill_service

        count = await skill_service.seed_from_directory(db, cfg.skills_dir)
        if count:
            logger.info("skills_seeded", count=count)

    # Seed MCP servers from legacy JSON files
    async with factory() as db:
        await _seed_mcp_servers(db, cfg)

    yield

    await close_engine()
    logger.info("shutdown_complete")


async def _seed_mcp_servers(db, cfg: AppConfig):
    """Import existing data/mcp_servers/*.json into DB on first boot."""
    from solomon.services import mcp_service

    mcp_dir = Path(cfg.data_dir) / "mcp_servers"
    if not mcp_dir.is_dir():
        return

    import json

    for json_file in mcp_dir.glob("*.json"):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            servers = data.get("servers", [])
            user_id = json_file.stem  # filename without extension = user_id
            for server in servers:
                if not isinstance(server, dict) or not server.get("url"):
                    continue
                # Only seed if not already in DB
                existing = await mcp_service.get_server(db, user_id, str(server.get("id", "")))
                if existing is None:
                    await mcp_service.save_server(db, user_id, server)
                    logger.info("mcp_server_seeded", user_id=user_id, server_name=server.get("name"))
        except Exception as exc:
            logger.warning("mcp_seed_failed", file=str(json_file), error=str(exc))


def create_app() -> FastAPI:
    cfg = get_config()

    app = FastAPI(
        title="Solomon",
        version="0.1.0",
        description="Conversational AI assistant with skills and MCP tool integration.",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[cfg.cors_origin] if cfg.cors_origin != "*" else ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Error handler
    from solomon.middleware.error_handler import ErrorHandlerMiddleware

    app.add_middleware(ErrorHandlerMiddleware)

    # API routers
    from solomon.api import chat, conversations, health, mcp, sessions, skills

    app.include_router(health.router)
    app.include_router(sessions.router)
    app.include_router(skills.router)
    app.include_router(conversations.router)
    app.include_router(mcp.router)
    app.include_router(chat.router)

    # Static files – serve frontend from public/ directory
    public_dir = Path(__file__).resolve().parent.parent.parent / "public"
    if public_dir.is_dir():
        app.mount("/", StaticFiles(directory=str(public_dir), html=True), name="static")

    return app


def cli():
    cfg = get_config()
    uvicorn.run(
        "solomon.main:create_app",
        factory=True,
        host=cfg.host,
        port=cfg.port,
        log_level="info",
    )


if __name__ == "__main__":
    cli()
