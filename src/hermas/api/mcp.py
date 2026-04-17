"""MCP server management and tool endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from hermas.api.dependencies import get_db, require_session
from hermas.schemas.mcp import MCPCallToolRequest, MCPServerCreate, MCPToolRequest
from hermas.services import mcp_service

router = APIRouter(prefix="/api/mcp", tags=["mcp"])


@router.post("/tools")
async def list_tools(
    body: MCPToolRequest,
    user_id: Annotated[str, Depends(require_session)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    server = await mcp_service.get_server(db, user_id, body.serverId)
    if server is None:
        raise HTTPException(404, detail="Server not found")
    tools = await mcp_service.list_tools_from_payload(server)
    return {"userId": user_id, "tools": tools}


@router.post("/call")
async def call_tool(
    body: MCPCallToolRequest,
    user_id: Annotated[str, Depends(require_session)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    server = await mcp_service.get_server(db, user_id, body.serverId)
    if server is None:
        raise HTTPException(404, detail="Server not found")
    result = await mcp_service.call_tool_from_payload(server, body.toolName, body.arguments)
    return {"userId": user_id, "result": result}


@router.get("/servers")
async def list_servers(
    user_id: Annotated[str, Depends(require_session)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    servers = await mcp_service.list_servers(db, user_id)
    return {"userId": user_id, "servers": servers}


@router.post("/servers")
async def save_server(
    body: MCPServerCreate,
    user_id: Annotated[str, Depends(require_session)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    saved = await mcp_service.save_server(db, user_id, body.model_dump())
    return {"userId": user_id, "server": saved}


@router.delete("/servers/{server_id}")
async def delete_server(
    server_id: str,
    user_id: Annotated[str, Depends(require_session)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    deleted = await mcp_service.delete_server(db, user_id, server_id)
    if not deleted:
        raise HTTPException(404, detail="Server not found")
    return {"userId": user_id, "deleted": True}
