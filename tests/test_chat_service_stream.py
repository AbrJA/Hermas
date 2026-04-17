"""Additional chat service tests for streaming and tool loop."""

from unittest.mock import AsyncMock, patch

import pytest

from hermas.schemas.common import LLMResult, LLMUsage
from hermas.services.chat_service import (
    _chat_context,
    _chat_with_tools,
    complete_chat_stream,
)


@pytest.mark.asyncio
async def test_chat_context(db_session, app_config):
    payload = {
        "messages": [{"role": "user", "content": "Hello"}],
        "model": "gpt-4",
        "temperature": 0.5,
        "maxTokens": 500,
    }

    with (
        patch("hermas.services.chat_service.prompt_builder.build_system_prompt", new_callable=AsyncMock, return_value=("System", [])),
        patch("hermas.services.chat_service.prompt_builder.append_mcp_context", new_callable=AsyncMock, return_value="System"),
    ):
        ctx = await _chat_context(payload, "alice", app_config, db_session)
        assert ctx["model"] == "gpt-4"
        assert ctx["temperature"] == 0.5
        assert ctx["max_tokens"] == 500
        assert len(ctx["messages"]) == 1


@pytest.mark.asyncio
async def test_chat_with_tools_no_mcp(app_config):
    ctx = {
        "messages": [{"role": "user", "content": "Hi"}],
        "model": "gpt-4",
        "base_url": "https://api.openai.com",
        "api_key": "key",
        "temperature": 0.2,
        "max_tokens": 1200,
        "system_prompt": "You are helpful.",
        "applied_skill_ids": [],
        "mcp_configs": {},
    }

    mock_result = LLMResult(content="Hello!", model="gpt-4", usage=LLMUsage())
    with patch("hermas.services.chat_service.llm_client.chat_completion", new_callable=AsyncMock, return_value=mock_result):
        result = await _chat_with_tools(app_config, ctx)
        assert result == "Hello!"


@pytest.mark.asyncio
async def test_chat_with_tools_tool_call(app_config):
    from hermas.services.mcp_client import MCPServerConfig

    ctx = {
        "messages": [{"role": "user", "content": "Query the DB"}],
        "model": "gpt-4",
        "base_url": "https://api.openai.com",
        "api_key": "key",
        "temperature": 0.2,
        "max_tokens": 1200,
        "system_prompt": "You are helpful.",
        "applied_skill_ids": [],
        "mcp_configs": {"mysql": MCPServerConfig(url="http://localhost:8000/mcp")},
    }

    # First LLM call returns a tool_call, second returns final answer
    tool_call_content = '<tool_call>\n{"server": "mysql", "tool": "run_query", "arguments": {"query": "SELECT 1"}}\n</tool_call>'
    result1 = LLMResult(content=tool_call_content, model="gpt-4", usage=LLMUsage())
    result2 = LLMResult(content="The result is 1.", model="gpt-4", usage=LLMUsage())

    call_count = 0

    async def mock_completion(**kwargs):
        nonlocal call_count
        call_count += 1
        return result1 if call_count == 1 else result2

    with (
        patch("hermas.services.chat_service.llm_client.chat_completion", side_effect=mock_completion),
        patch("hermas.services.chat_service.mcp_client_mod.call_tool", new_callable=AsyncMock, return_value={"content": [{"type": "text", "text": "1"}]}),
    ):
        result = await _chat_with_tools(app_config, ctx)
        assert result == "The result is 1."


@pytest.mark.asyncio
async def test_complete_chat_stream(db_session, app_config):
    """Test that streaming yields start, token, and done events."""

    async def mock_stream(**kwargs):
        for chunk in ["Hello", " world", "!"]:
            yield chunk

    with (
        patch("hermas.services.chat_service.prompt_builder.build_system_prompt", new_callable=AsyncMock, return_value=("System", [])),
        patch("hermas.services.chat_service.prompt_builder.append_mcp_context", new_callable=AsyncMock, return_value="System"),
        patch("hermas.services.chat_service.llm_client.chat_completion_stream", side_effect=mock_stream),
    ):
        payload = {"messages": [{"role": "user", "content": "Hi"}]}
        events = []
        async for event in complete_chat_stream(app_config, "alice", payload, db_session):
            events.append(event)

        assert len(events) >= 3  # start + tokens + done
        assert "event: start" in events[0]
        assert "event: done" in events[-1]
        # Check token events exist
        token_events = [e for e in events if "event: token" in e]
        assert len(token_events) >= 1
