"""MCP server / tool schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MCPServerCreate(BaseModel):
    id: str = ""
    name: str = "MCP Server"
    url: str
    authHeaderName: str = ""
    authHeaderValue: str = ""
    enabled: bool = True
    timeoutSeconds: int = 15


class MCPServerResponse(BaseModel):
    id: str
    name: str
    url: str
    authHeaderName: str
    authHeaderValue: str
    enabled: bool
    timeoutSeconds: int = 15


class MCPToolRequest(BaseModel):
    serverId: str


class MCPCallToolRequest(BaseModel):
    serverId: str
    toolName: str
    arguments: dict = Field(default_factory=dict)
