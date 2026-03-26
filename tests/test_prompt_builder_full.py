"""Tests for prompt_builder async functions with mocked dependencies."""

from unittest.mock import AsyncMock, patch

import pytest

from hermas.services.mcp_client import MCPServerConfig
from hermas.services.prompt_builder import (
    _build_skill_context,
    append_mcp_context,
    build_system_prompt,
)


@pytest.mark.asyncio
async def test_build_skill_context_empty(db_session):
    result = await _build_skill_context([], db_session)
    assert result == ""


@pytest.mark.asyncio
async def test_build_skill_context_with_skills(db_session):
    from hermas.services import skill_service

    await skill_service.create_skill(
        db_session,
        skill_id="ctx-test",
        name="Context Test",
        content="Do context things.",
    )
    result = await _build_skill_context(["ctx-test"], db_session)
    assert "Context Test" in result
    assert "Do context things." in result


@pytest.mark.asyncio
async def test_build_system_prompt_no_skills(db_session, app_config):
    with patch("hermas.services.prompt_builder.skill_routing_service.resolve_skill_ids", new_callable=AsyncMock, return_value=[]):
        prompt, skill_ids = await build_system_prompt(
            {}, app_config, [{"role": "user", "content": "Hi"}],
            "test-key", "https://api.openai.com", "gpt-4", db_session,
        )
        assert app_config.system_prompt in prompt
        assert skill_ids == []
        assert "No optional skill" in prompt


@pytest.mark.asyncio
async def test_build_system_prompt_with_custom(db_session, app_config):
    with patch("hermas.services.prompt_builder.skill_routing_service.resolve_skill_ids", new_callable=AsyncMock, return_value=[]):
        prompt, _ = await build_system_prompt(
            {"systemPrompt": "Be creative"},
            app_config,
            [{"role": "user", "content": "Hi"}],
            "test-key", "https://api.openai.com", "gpt-4", db_session,
        )
        assert "Be creative" in prompt


@pytest.mark.asyncio
async def test_build_system_prompt_with_skills(db_session, app_config):
    from hermas.services import skill_service

    await skill_service.create_skill(
        db_session, skill_id="pb-skill", name="PB Skill", content="Special instructions"
    )

    with patch("hermas.services.prompt_builder.skill_routing_service.resolve_skill_ids", new_callable=AsyncMock, return_value=["pb-skill"]):
        prompt, skill_ids = await build_system_prompt(
            {}, app_config, [{"role": "user", "content": "Hi"}],
            "test-key", "https://api.openai.com", "gpt-4", db_session,
        )
        assert "pb-skill" in skill_ids
        assert "Special instructions" in prompt
        assert "transient" in prompt.lower()


@pytest.mark.asyncio
async def test_append_mcp_context_no_configs(db_session):
    result = await append_mcp_context("Base prompt", {}, db_session)
    assert result == "Base prompt"


@pytest.mark.asyncio
async def test_append_mcp_context_with_tools(db_session):
    configs = {"test-server": MCPServerConfig(url="http://localhost:8000/mcp")}

    with patch("hermas.services.prompt_builder.mcp_client.list_tools", new_callable=AsyncMock) as mock_list:
        mock_list.return_value = [
            {"name": "query", "description": "Run a query", "inputSchema": {"properties": {"sql": {}}}}
        ]
        result = await append_mcp_context("Base prompt", configs, db_session)
        assert "query" in result
        assert "Base prompt" in result
