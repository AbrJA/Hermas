"""Tests for sessions API endpoints."""

import pytest


@pytest.mark.asyncio
async def test_create_session(client, app_config):
    resp = await client.post(
        "/api/session",
        json={"userId": "alice"},
        headers={"X-App-Token": app_config.app_api_token},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "sessionToken" in data
    assert "expiresAt" in data
    assert isinstance(data["sessionToken"], str)
    assert len(data["sessionToken"]) == 36


@pytest.mark.asyncio
async def test_create_session_no_auth(client):
    """With require_auth=False, sessions are created without token."""
    resp = await client.post(
        "/api/session",
        json={"userId": "alice"},
    )
    # Auth not required in test config
    assert resp.status_code == 200
    data = resp.json()
    assert "sessionToken" in data


@pytest.mark.asyncio
async def test_create_session_with_empty_user(client):
    resp = await client.post(
        "/api/session",
        json={"userId": ""},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["userId"].startswith("user-")
