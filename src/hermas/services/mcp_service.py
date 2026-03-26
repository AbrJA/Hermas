"""MCP server management service – DB-backed CRUD + tool operations."""

from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from hermas.models.mcp_server import MCPServer
from hermas.services import mcp_client


def _safe_user_id(user_id: str) -> str:
    import re

    cleaned = re.sub(r"[^a-z0-9_-]+", "-", user_id.strip().lower())
    return cleaned or "anonymous"


# ---------------------------------------------------------------------------
# Server CRUD
# ---------------------------------------------------------------------------


async def list_servers(db: AsyncSession, user_id: str) -> list[dict]:
    safe = _safe_user_id(user_id)
    result = await db.execute(select(MCPServer).where(MCPServer.user_id == safe))
    return [
        {
            "id": s.id,
            "name": s.name,
            "url": s.url,
            "authHeaderName": s.auth_header_name,
            "authHeaderValue": s.auth_header_value,
            "enabled": s.enabled,
            "timeoutSeconds": s.timeout_seconds,
        }
        for s in result.scalars()
    ]


async def get_server(db: AsyncSession, user_id: str, server_id: str) -> dict | None:
    safe = _safe_user_id(user_id)
    result = await db.execute(
        select(MCPServer).where(MCPServer.id == server_id, MCPServer.user_id == safe)
    )
    s = result.scalar_one_or_none()
    if s is None:
        return None
    return {
        "id": s.id,
        "name": s.name,
        "url": s.url,
        "authHeaderName": s.auth_header_name,
        "authHeaderValue": s.auth_header_value,
        "enabled": s.enabled,
        "timeoutSeconds": s.timeout_seconds,
    }


async def save_server(db: AsyncSession, user_id: str, payload: dict) -> dict:
    safe = _safe_user_id(user_id)
    server_id = str(payload.get("id", "")).strip()
    if not server_id:
        server_id = str(uuid.uuid4())

    result = await db.execute(select(MCPServer).where(MCPServer.id == server_id, MCPServer.user_id == safe))
    existing = result.scalar_one_or_none()

    if existing is not None:
        existing.name = str(payload.get("name", existing.name))
        existing.url = str(payload.get("url", existing.url))
        existing.auth_header_name = str(payload.get("authHeaderName", existing.auth_header_name))
        existing.auth_header_value = str(payload.get("authHeaderValue", existing.auth_header_value))
        existing.enabled = bool(payload.get("enabled", existing.enabled))
        existing.timeout_seconds = int(payload.get("timeoutSeconds", existing.timeout_seconds))
        await db.commit()
        await db.refresh(existing)
        entry = existing
    else:
        entry = MCPServer(
            id=server_id,
            user_id=safe,
            name=str(payload.get("name", "MCP Server")),
            url=str(payload.get("url", "")),
            auth_header_name=str(payload.get("authHeaderName", "")),
            auth_header_value=str(payload.get("authHeaderValue", "")),
            enabled=bool(payload.get("enabled", True)),
            timeout_seconds=int(payload.get("timeoutSeconds", 15)),
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)

    return {
        "id": entry.id,
        "name": entry.name,
        "url": entry.url,
        "authHeaderName": entry.auth_header_name,
        "authHeaderValue": entry.auth_header_value,
        "enabled": entry.enabled,
        "timeoutSeconds": entry.timeout_seconds,
    }


async def delete_server(db: AsyncSession, user_id: str, server_id: str) -> bool:
    safe = _safe_user_id(user_id)
    result = await db.execute(
        delete(MCPServer).where(MCPServer.id == server_id, MCPServer.user_id == safe)
    )
    await db.commit()
    return (result.rowcount or 0) > 0


# ---------------------------------------------------------------------------
# Tool operations (delegates to mcp_client)
# ---------------------------------------------------------------------------


def _config_from_payload(server_dict: dict) -> mcp_client.MCPServerConfig:
    url = str(server_dict.get("url", "")).strip()
    if not url:
        raise ValueError("server.url is required")
    return mcp_client.MCPServerConfig(
        url=url,
        auth_header_name=str(server_dict.get("authHeaderName", "")),
        auth_header_value=str(server_dict.get("authHeaderValue", "")),
        timeout_seconds=int(server_dict.get("timeoutSeconds", 15)),
    )


async def list_tools_from_payload(server_dict: dict) -> list[dict]:
    cfg = _config_from_payload(server_dict)
    return await mcp_client.list_tools(cfg)


async def call_tool_from_payload(server_dict: dict, tool_name: str, arguments: dict) -> dict:
    cfg = _config_from_payload(server_dict)
    return await mcp_client.call_tool(cfg, tool_name, arguments)
