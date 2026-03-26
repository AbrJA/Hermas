"""Tests for chat_service async flows with mocked LLM."""

from unittest.mock import AsyncMock, patch

import pytest

from hermas.services.chat_service import (
    _execute_tool,
    complete_chat,
)
from hermas.services.mcp_client import MCPServerConfig


@pytest.mark.asyncio
async def test_execute_tool_unknown_server():
    tool_call = {"server": "nonexistent", "tool": "my_tool", "arguments": {}}
    result = await _execute_tool(tool_call, {})
    assert "Error: Unknown MCP server" in result


@pytest.mark.asyncio
async def test_execute_tool_exception():
    tool_call = {"server": "test", "tool": "broken_tool", "arguments": {}}
    config = MCPServerConfig(url="http://localhost:8000/mcp")

    with patch("hermas.services.chat_service.mcp_client_mod.call_tool", side_effect=RuntimeError("Connection failed")):
        result = await _execute_tool(tool_call, {"test": config})
        assert "Error calling tool 'broken_tool'" in result


@pytest.mark.asyncio
async def test_execute_tool_success():
    tool_call = {"server": "test", "tool": "my_tool", "arguments": {"q": "hello"}}
    config = MCPServerConfig(url="http://localhost:8000/mcp")

    with patch("hermas.services.chat_service.mcp_client_mod.call_tool", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = {"content": [{"type": "text", "text": "Result data"}]}
        result = await _execute_tool(tool_call, {"test": config})
        assert result == "Result data"


@pytest.mark.asyncio
async def test_execute_tool_truncation():
    tool_call = {"server": "test", "tool": "big_tool", "arguments": {}}
    config = MCPServerConfig(url="http://localhost:8000/mcp")

    with patch("hermas.services.chat_service.mcp_client_mod.call_tool", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = {"content": [{"type": "text", "text": "X" * 10000}]}
        result = await _execute_tool(tool_call, {"test": config})
        assert "truncated" in result


@pytest.mark.asyncio
async def test_complete_chat_mocked(db_session, app_config):
    """Test complete_chat with mocked LLM and prompt builder."""
    from hermas.schemas.common import LLMResult, LLMUsage

    mock_llm_result = LLMResult(content="Hello from assistant", model="gpt-4", usage=LLMUsage())

    payload = {
        "messages": [{"role": "user", "content": "Hello"}],
        "model": "gpt-4",
        "conversationId": "test-conv",
    }

    with (
        patch("hermas.services.chat_service.llm_client.chat_completion", new_callable=AsyncMock, return_value=mock_llm_result),
        patch("hermas.services.chat_service.prompt_builder.build_system_prompt", new_callable=AsyncMock, return_value=("System prompt", [])),
        patch("hermas.services.chat_service.prompt_builder.append_mcp_context", new_callable=AsyncMock, return_value="System prompt"),
    ):
        result = await complete_chat(app_config, "alice", payload, db_session)
        assert result["conversationId"] == "test-conv"
        assert result["content"] == "Hello from assistant"
        assert result["model"] == "gpt-4"
