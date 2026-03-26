"""Tests for skills API endpoints."""

import pytest


@pytest.mark.asyncio
async def test_list_skills(client):
    resp = await client.get("/api/skills")
    assert resp.status_code == 200
    data = resp.json()
    assert "skills" in data
    assert isinstance(data["skills"], list)


@pytest.mark.asyncio
async def test_create_and_get_skill(client):
    resp = await client.post(
        "/api/skills",
        json={
            "name": "Test Skill",
            "description": "A test skill",
            "content": "Do things in a special way.",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    skill = data["skill"]
    assert skill["name"] == "Test Skill"
    skill_id = skill["id"]

    # Retrieve
    resp2 = await client.get(f"/api/skills/{skill_id}")
    assert resp2.status_code == 200
    assert resp2.json()["name"] == "Test Skill"


@pytest.mark.asyncio
async def test_delete_skill(client):
    resp = await client.post(
        "/api/skills",
        json={"name": "To Delete", "content": "X"},
    )
    skill_id = resp.json()["skill"]["id"]

    resp2 = await client.delete(f"/api/skills/{skill_id}")
    assert resp2.status_code == 200

    # Confirm deleted
    resp3 = await client.get(f"/api/skills/{skill_id}")
    assert resp3.status_code == 404


@pytest.mark.asyncio
async def test_get_nonexistent_skill(client):
    resp = await client.get("/api/skills/nonexistent")
    assert resp.status_code == 404
