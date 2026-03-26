"""MCP (Model Context Protocol) JSON-RPC client over HTTP with SSE support.

Ported from Julia MCPClient.jl with async httpx.
"""

from __future__ import annotations

import json
import time

import httpx
import structlog

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Session cache – keyed by (url, auth_header_name, auth_header_value)
# ---------------------------------------------------------------------------

_session_ids: dict[tuple[str, str, str], str] = {}


class MCPServerConfig:
    """Configuration for a single MCP server endpoint."""

    __slots__ = ("auth_header_name", "auth_header_value", "timeout_seconds", "url")

    def __init__(
        self,
        url: str,
        auth_header_name: str = "",
        auth_header_value: str = "",
        timeout_seconds: int = 15,
    ):
        self.url = url
        self.auth_header_name = auth_header_name
        self.auth_header_value = auth_header_value
        self.timeout_seconds = timeout_seconds

    def _session_key(self) -> tuple[str, str, str]:
        return (self.url, self.auth_header_name, self.auth_header_value)


def _headers(server: MCPServerConfig) -> dict[str, str]:
    h = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    if server.auth_header_name and server.auth_header_value:
        h[server.auth_header_name] = server.auth_header_value
    return h


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------


async def _initialize_session(server: MCPServerConfig) -> str:
    payload = {
        "jsonrpc": "2.0",
        "id": str(time.time_ns()),
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "hermas", "version": "1.0.0"},
        },
    }

    async with httpx.AsyncClient(timeout=server.timeout_seconds) as client:
        resp = await client.post(server.url, headers=_headers(server), content=json.dumps(payload))

    if resp.status_code < 200 or resp.status_code >= 300:
        raise RuntimeError(f"MCP initialize failed with status {resp.status_code}")

    session_id = resp.headers.get("mcp-session-id", "")
    if not session_id:
        raise RuntimeError("MCP initialize did not return mcp-session-id")

    # Best-effort initialized notification
    try:
        notify_payload = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        }
        notify_headers = {**_headers(server), "mcp-session-id": session_id}
        async with httpx.AsyncClient(timeout=server.timeout_seconds) as client:
            await client.post(server.url, headers=notify_headers, content=json.dumps(notify_payload))
    except Exception:
        pass

    _session_ids[server._session_key()] = session_id
    return session_id


async def _get_session_id(server: MCPServerConfig) -> str:
    existing = _session_ids.get(server._session_key(), "")
    if existing:
        return existing
    return await _initialize_session(server)


# ---------------------------------------------------------------------------
# SSE parsing
# ---------------------------------------------------------------------------


def _extract_json_from_sse(body: str) -> dict:
    data_lines: list[str] = []
    for raw_line in body.split("\n"):
        line = raw_line.strip()
        if not line or line.startswith(":"):
            continue
        if line.startswith("data:"):
            payload = line[5:].strip()
            if payload:
                data_lines.append(payload)

    for payload in data_lines:
        try:
            parsed = json.loads(payload)
            if isinstance(parsed, dict) and ("result" in parsed or "error" in parsed):
                return parsed
        except json.JSONDecodeError:
            continue

    if data_lines:
        combined = "\n".join(data_lines)
        parsed = json.loads(combined)
        if isinstance(parsed, dict) and ("result" in parsed or "error" in parsed):
            return parsed

    raise RuntimeError("MCP SSE response did not include a JSON-RPC payload")


def _parse_jsonrpc_response(response: httpx.Response) -> dict:
    body = response.text
    content_type = response.headers.get("content-type", "").lower()

    if (
        "text/event-stream" in content_type
        or body.lstrip().startswith("event:")
        or body.lstrip().startswith("data:")
    ):
        return _extract_json_from_sse(body)

    return json.loads(body)


# ---------------------------------------------------------------------------
# Generic JSON-RPC call
# ---------------------------------------------------------------------------


async def _jsonrpc(server: MCPServerConfig, method: str, params: dict) -> dict:
    payload = {
        "jsonrpc": "2.0",
        "id": str(time.time_ns()),
        "method": method,
        "params": params,
    }

    session_id = await _get_session_id(server)
    headers = {**_headers(server), "mcp-session-id": session_id}

    async with httpx.AsyncClient(timeout=server.timeout_seconds) as client:
        resp = await client.post(server.url, headers=headers, content=json.dumps(payload))

    # Retry once on 400 (stale session)
    if resp.status_code == 400:
        _session_ids[server._session_key()] = ""
        session_id = await _get_session_id(server)
        headers["mcp-session-id"] = session_id
        async with httpx.AsyncClient(timeout=server.timeout_seconds) as client:
            resp = await client.post(server.url, headers=headers, content=json.dumps(payload))

    if resp.status_code < 200 or resp.status_code >= 300:
        raise RuntimeError(f"MCP server returned status {resp.status_code}")

    parsed = _parse_jsonrpc_response(resp)

    if "error" in parsed:
        raise RuntimeError(f"MCP error: {json.dumps(parsed['error'])}")

    if "result" not in parsed:
        raise RuntimeError("MCP response did not include result")

    return parsed["result"]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def list_tools(server: MCPServerConfig) -> list[dict]:
    result = await _jsonrpc(server, "tools/list", {})
    tools = result.get("tools", [])
    return tools if isinstance(tools, list) else []


async def call_tool(server: MCPServerConfig, tool_name: str, arguments: dict) -> dict:
    return await _jsonrpc(server, "tools/call", {"name": tool_name, "arguments": arguments})
