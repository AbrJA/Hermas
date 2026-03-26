"""Tests for conversations API endpoints."""

import pytest


@pytest.mark.asyncio
async def test_list_conversations_empty(client):
    resp = await client.get("/api/conversations/list")
    assert resp.status_code == 200
    data = resp.json()
    assert "conversations" in data


@pytest.mark.asyncio
async def test_load_nonexistent_conversation(client):
    resp = await client.get("/api/conversations/load", params={"id": "nonexistent"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_search_conversations(client):
    resp = await client.get("/api/conversations/search", params={"q": "hello"})
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
