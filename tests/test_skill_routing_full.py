"""Tests for skill routing service with mocked LLM."""

from unittest.mock import AsyncMock, patch

import pytest

from hermas.services.skill_routing_service import resolve_skill_ids


@pytest.mark.asyncio
async def test_resolve_no_skill_ids(db_session, app_config):
    result = await resolve_skill_ids(
        {}, "alice", app_config, [{"role": "user", "content": "Hi"}],
        "key", "https://api.openai.com", "gpt-4", db_session,
    )
    assert result == []


@pytest.mark.asyncio
async def test_resolve_no_auto_routing(db_session, app_config):
    result = await resolve_skill_ids(
        {"selectedSkillIds": ["a", "b"], "autoSkillRouting": False},
        "alice",
        app_config,
        [{"role": "user", "content": "Hi"}],
        "key", "https://api.openai.com", "gpt-4", db_session,
    )
    assert result == ["a", "b"]


@pytest.mark.asyncio
async def test_resolve_auto_routing_with_match(db_session, app_config):
    from hermas.services import skill_service

    await skill_service.create_skill(
        db_session, skill_id="pirate-translator", name="Pirate Translator",
        description="Translates to pirate", content="Talk like a pirate", user_id="alice"
    )

    with patch("hermas.services.skill_routing_service.llm_client.route_skills", new_callable=AsyncMock, return_value=["pirate-translator"]):
        result = await resolve_skill_ids(
            {"selectedSkillIds": ["pirate-translator"], "autoSkillRouting": True},
            "alice",
            app_config,
            [{"role": "user", "content": "Translate to pirate"}],
            "key", "https://api.openai.com", "gpt-4", db_session,
        )
        assert result == ["pirate-translator"]


@pytest.mark.asyncio
async def test_resolve_auto_routing_multiple_skills(db_session, app_config):
    from hermas.services import skill_service

    await skill_service.create_skill(
        db_session, skill_id="summarizer", name="Summarizer",
        description="Summarizes text", content="Make summaries", user_id="alice"
    )
    await skill_service.create_skill(
        db_session, skill_id="reviewer", name="Code Reviewer",
        description="Reviews code", content="Review code", user_id="alice"
    )

    with patch("hermas.services.skill_routing_service.llm_client.route_skills", new_callable=AsyncMock, return_value=["summarizer", "reviewer"]):
        result = await resolve_skill_ids(
            {"selectedSkillIds": ["summarizer", "reviewer"], "autoSkillRouting": True},
            "alice",
            app_config,
            [{"role": "user", "content": "Summarize and review this code"}],
            "key", "https://api.openai.com", "gpt-4", db_session,
        )
        assert result == ["summarizer", "reviewer"]


@pytest.mark.asyncio
async def test_resolve_auto_routing_no_match(db_session, app_config):
    from hermas.services import skill_service

    await skill_service.create_skill(
        db_session, skill_id="routing-test", name="Test",
        description="Test skill", content="Do stuff", user_id="alice"
    )

    with patch("hermas.services.skill_routing_service.llm_client.route_skills", new_callable=AsyncMock, return_value=[]):
        result = await resolve_skill_ids(
            {"selectedSkillIds": ["routing-test"], "autoSkillRouting": True},
            "alice",
            app_config,
            [{"role": "user", "content": "Something unrelated"}],
            "key", "https://api.openai.com", "gpt-4", db_session,
        )
        assert result == []


@pytest.mark.asyncio
async def test_resolve_no_user_query(db_session, app_config):
    from hermas.services import skill_service

    await skill_service.create_skill(
        db_session, skill_id="noq-test", name="NoQ",
        description="Test", content="Content", user_id="alice"
    )

    result = await resolve_skill_ids(
        {"selectedSkillIds": ["noq-test"], "autoSkillRouting": True},
        "alice",
        app_config,
        [{"role": "assistant", "content": "Hello"}],
        "key", "https://api.openai.com", "gpt-4", db_session,
    )
    assert result == []
