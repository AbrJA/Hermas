"""Tests for skill service."""

import pytest

from solomon.services import skill_service


@pytest.mark.asyncio
async def test_create_and_get_skill(db_session):
    result = await skill_service.create_skill(
        db_session,
        skill_id="test-skill",
        name="Test Skill",
        description="A test skill",
        content="Do things differently.",
    )
    assert result["id"] == "test-skill"
    assert result["name"] == "Test Skill"

    skill = await skill_service.get_skill(db_session, "test-skill")
    assert skill is not None
    assert skill["content"] == "Do things differently."


@pytest.mark.asyncio
async def test_list_skills(db_session):
    await skill_service.create_skill(db_session, name="Skill A", content="Content A")
    await skill_service.create_skill(db_session, name="Skill B", content="Content B")

    skill_service.invalidate_cache()
    skills = await skill_service.list_skills(db_session)
    assert len(skills) >= 2
    names = [s["name"] for s in skills]
    assert "Skill A" in names
    assert "Skill B" in names


@pytest.mark.asyncio
async def test_update_skill(db_session):
    await skill_service.create_skill(db_session, skill_id="upd-skill", name="Original", content="V1")
    result = await skill_service.update_skill(db_session, skill_id="upd-skill", name="Updated", content="V2")
    assert result["name"] == "Updated"
    assert result["content"] == "V2"


@pytest.mark.asyncio
async def test_delete_skill(db_session):
    await skill_service.create_skill(db_session, skill_id="del-skill", name="ToDelete", content="X")
    deleted = await skill_service.delete_skill(db_session, "del-skill")
    assert deleted is True

    skill = await skill_service.get_skill(db_session, "del-skill")
    assert skill is None


@pytest.mark.asyncio
async def test_delete_nonexistent_skill(db_session):
    deleted = await skill_service.delete_skill(db_session, "nonexistent")
    assert deleted is False


@pytest.mark.asyncio
async def test_upload_skill_md(db_session):
    markdown = """---
name: Pirate Translator
description: Translates to pirate speak
id: pirate-translator
---

You MUST translate everything to pirate speak.
"""
    result = await skill_service.upload_skill_md(db_session, markdown)
    assert result["id"] == "pirate-translator"
    assert result["name"] == "Pirate Translator"
    assert "pirate speak" in result["content"]


def test_parse_frontmatter():
    md = """---
name: Test
description: A test skill
id: test-id
---

Body content here.
"""
    fm, body = skill_service.parse_frontmatter(md)
    assert fm["name"] == "Test"
    assert fm["description"] == "A test skill"
    assert fm["id"] == "test-id"
    assert "Body content here." in body


def test_parse_frontmatter_no_frontmatter():
    md = "Just plain text."
    fm, body = skill_service.parse_frontmatter(md)
    assert fm == {}
    assert body == md


def test_normalize_skill_id():
    from solomon.services.skill_service import _normalize_skill_id

    assert _normalize_skill_id("Hello World!") == "hello-world"
    assert _normalize_skill_id("ELI5 Expert") == "eli5-expert"
    assert _normalize_skill_id("already-kebab") == "already-kebab"
