"""Tests for MCP client helpers."""


import pytest

from hermas.services.mcp_client import (
    MCPServerConfig,
    _extract_json_from_sse,
    _headers,
)


def test_mcp_server_config():
    cfg = MCPServerConfig(url="http://localhost:8000/mcp")
    assert cfg.url == "http://localhost:8000/mcp"
    assert cfg.auth_header_name == ""
    assert cfg.timeout_seconds == 15


def test_headers_without_auth():
    cfg = MCPServerConfig(url="http://localhost:8000/mcp")
    h = _headers(cfg)
    assert "Content-Type" in h
    assert "Authorization" not in h


def test_headers_with_auth():
    cfg = MCPServerConfig(
        url="http://localhost:8000/mcp",
        auth_header_name="Authorization",
        auth_header_value="Bearer secret",
    )
    h = _headers(cfg)
    assert h["Authorization"] == "Bearer secret"


def test_extract_json_from_sse_single_line():
    body = 'event: message\ndata: {"jsonrpc":"2.0","id":"1","result":{"tools":[]}}\n\n'
    parsed = _extract_json_from_sse(body)
    assert "result" in parsed
    assert parsed["result"]["tools"] == []


def test_extract_json_from_sse_with_error():
    body = 'data: {"jsonrpc":"2.0","id":"1","error":{"code":-32600,"message":"bad"}}\n\n'
    parsed = _extract_json_from_sse(body)
    assert "error" in parsed


def test_extract_json_from_sse_no_payload():
    with pytest.raises(RuntimeError, match="JSON-RPC payload"):
        _extract_json_from_sse("event: message\ndata: {}\n\n")


def test_session_key():
    cfg = MCPServerConfig(
        url="http://localhost:8000/mcp",
        auth_header_name="Authorization",
        auth_header_value="Bearer x",
    )
    key = cfg._session_key()
    assert key == ("http://localhost:8000/mcp", "Authorization", "Bearer x")
