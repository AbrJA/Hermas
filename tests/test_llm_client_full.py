"""Tests for LLM client with mocked OpenAI."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from solomon.schemas.common import LLMUsage
from solomon.services.llm_client import (
    _get_client,
    _parse_usage,
    chat_completion,
    route_skill,
)


def test_get_client_no_key():
    with pytest.raises(ValueError, match="No API key"):
        _get_client("https://api.openai.com", "")


def test_get_client_creates_client():
    from solomon.services.llm_client import _clients
    _clients.clear()
    client = _get_client("https://api.openai.com", "test-key")
    assert client is not None
    # Second call returns cached
    client2 = _get_client("https://api.openai.com", "test-key")
    assert client is client2
    _clients.clear()


def test_parse_usage_none():
    usage = _parse_usage(None)
    assert isinstance(usage, LLMUsage)
    assert usage.input_tokens == 0
    assert usage.output_tokens == 0


def test_parse_usage_object():
    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 100
    mock_usage.completion_tokens = 200
    usage = _parse_usage(mock_usage)
    assert usage.input_tokens == 100
    assert usage.output_tokens == 200


@pytest.mark.asyncio
async def test_chat_completion_mocked():
    mock_choice = MagicMock()
    mock_choice.message.content = "Hello from LLM"

    mock_usage_obj = MagicMock()
    mock_usage_obj.prompt_tokens = 10
    mock_usage_obj.completion_tokens = 20

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage = mock_usage_obj
    mock_response.model = "gpt-4"

    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    with patch("solomon.services.llm_client._get_client", return_value=mock_client):
        result = await chat_completion(
            base_url="https://api.openai.com",
            api_key="test-key",
            model="gpt-4",
            messages=[{"role": "user", "content": "Hi"}],
        )
        assert result.content == "Hello from LLM"
        assert result.model == "gpt-4"
        assert result.usage.input_tokens == 10
        assert result.usage.output_tokens == 20


@pytest.mark.asyncio
async def test_route_skill_empty():
    result = await route_skill(
        base_url="https://api.openai.com",
        api_key="test-key",
        model="gpt-4",
        query="",
        skills=[],
    )
    assert result == ""


@pytest.mark.asyncio
async def test_route_skill_mocked():
    mock_skill = MagicMock()
    mock_skill.id = "pirate"
    mock_skill.name = "Pirate"
    mock_skill.description = "Talk like a pirate"

    mock_choice = MagicMock()
    mock_choice.message.content = "pirate"
    mock_usage_obj = MagicMock()
    mock_usage_obj.prompt_tokens = 5
    mock_usage_obj.completion_tokens = 1
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage = mock_usage_obj
    mock_response.model = "gpt-4"

    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    with patch("solomon.services.llm_client._get_client", return_value=mock_client):
        result = await route_skill(
            base_url="https://api.openai.com",
            api_key="test-key",
            model="gpt-4",
            query="Talk like a pirate",
            skills=[mock_skill],
        )
        assert result == "pirate"
