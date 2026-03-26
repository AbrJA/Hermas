"""Tests for MCP client async functions with mocked httpx."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from solomon.services.mcp_client import (
    MCPServerConfig,
    _get_session_id,
    _initialize_session,
    _jsonrpc,
    _parse_jsonrpc_response,
    _session_ids,
    call_tool,
    list_tools,
)


@pytest.fixture(autouse=True)
def clear_sessions():
    _session_ids.clear()
    yield
    _session_ids.clear()


@pytest.mark.asyncio
async def test_initialize_session():
    server = MCPServerConfig(url="http://localhost:8000/mcp")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"mcp-session-id": "test-session-123"}

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("solomon.services.mcp_client.httpx.AsyncClient", return_value=mock_client):
        session_id = await _initialize_session(server)
        assert session_id == "test-session-123"
        assert _session_ids[server._session_key()] == "test-session-123"


@pytest.mark.asyncio
async def test_initialize_session_failure():
    server = MCPServerConfig(url="http://localhost:8000/mcp")

    mock_resp = MagicMock()
    mock_resp.status_code = 500

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("solomon.services.mcp_client.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(RuntimeError, match="MCP initialize failed"):
            await _initialize_session(server)


@pytest.mark.asyncio
async def test_initialize_session_no_session_id():
    server = MCPServerConfig(url="http://localhost:8000/mcp")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {}

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("solomon.services.mcp_client.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(RuntimeError, match="mcp-session-id"):
            await _initialize_session(server)


@pytest.mark.asyncio
async def test_get_session_id_cached():
    server = MCPServerConfig(url="http://localhost:8000/mcp")
    _session_ids[server._session_key()] = "cached-id"
    session_id = await _get_session_id(server)
    assert session_id == "cached-id"


def test_parse_jsonrpc_response_json():
    resp = MagicMock()
    resp.text = '{"jsonrpc":"2.0","id":"1","result":{"tools":[]}}'
    resp.headers = {"content-type": "application/json"}
    parsed = _parse_jsonrpc_response(resp)
    assert "result" in parsed


def test_parse_jsonrpc_response_sse():
    resp = MagicMock()
    resp.text = 'event: message\ndata: {"jsonrpc":"2.0","id":"1","result":{"tools":[]}}\n\n'
    resp.headers = {"content-type": "text/event-stream"}
    parsed = _parse_jsonrpc_response(resp)
    assert "result" in parsed


@pytest.mark.asyncio
async def test_jsonrpc_success():
    server = MCPServerConfig(url="http://localhost:8000/mcp")
    _session_ids[server._session_key()] = "my-session"

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = '{"jsonrpc":"2.0","id":"1","result":{"tools":[{"name":"my_tool"}]}}'
    mock_resp.headers = {"content-type": "application/json"}

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("solomon.services.mcp_client.httpx.AsyncClient", return_value=mock_client):
        result = await _jsonrpc(server, "tools/list", {})
        assert "tools" in result
        assert result["tools"][0]["name"] == "my_tool"


@pytest.mark.asyncio
async def test_jsonrpc_retry_on_400():
    server = MCPServerConfig(url="http://localhost:8000/mcp")
    _session_ids[server._session_key()] = "stale-session"

    # First call returns 400, then re-init returns 200
    bad_resp = MagicMock()
    bad_resp.status_code = 400

    init_resp = MagicMock()
    init_resp.status_code = 200
    init_resp.headers = {"mcp-session-id": "new-session"}

    good_resp = MagicMock()
    good_resp.status_code = 200
    good_resp.text = '{"jsonrpc":"2.0","id":"1","result":{}}'
    good_resp.headers = {"content-type": "application/json"}

    call_count = 0

    mock_client = AsyncMock()

    async def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return bad_resp
        if call_count == 2:
            return init_resp
        if call_count == 3:
            return init_resp  # notifications/initialized
        return good_resp

    mock_client.post = AsyncMock(side_effect=side_effect)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("solomon.services.mcp_client.httpx.AsyncClient", return_value=mock_client):
        result = await _jsonrpc(server, "tools/list", {})
        assert isinstance(result, dict)  # _jsonrpc returns parsed["result"]


@pytest.mark.asyncio
async def test_list_tools():
    server = MCPServerConfig(url="http://localhost:8000/mcp")
    _session_ids[server._session_key()] = "sess"

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = json.dumps({
        "jsonrpc": "2.0", "id": "1",
        "result": {"tools": [{"name": "my_tool", "description": "A tool"}]},
    })
    mock_resp.headers = {"content-type": "application/json"}

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("solomon.services.mcp_client.httpx.AsyncClient", return_value=mock_client):
        tools = await list_tools(server)
        assert len(tools) == 1
        assert tools[0]["name"] == "my_tool"


@pytest.mark.asyncio
async def test_call_tool():
    server = MCPServerConfig(url="http://localhost:8000/mcp")
    _session_ids[server._session_key()] = "sess"

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = json.dumps({
        "jsonrpc": "2.0", "id": "1",
        "result": {"content": [{"type": "text", "text": "Result data"}]},
    })
    mock_resp.headers = {"content-type": "application/json"}

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("solomon.services.mcp_client.httpx.AsyncClient", return_value=mock_client):
        result = await call_tool(server, "my_tool", {"arg1": "val1"})
        assert "content" in result
