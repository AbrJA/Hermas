"""Tests for health endpoints."""

import pytest


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "hermas"


@pytest.mark.asyncio
async def test_readiness(client):
    resp = await client.get("/api/readiness")
    assert resp.status_code in (200, 503)
    data = resp.json()
    assert "ready" in data
    assert "checks" in data


@pytest.mark.asyncio
async def test_config(client):
    resp = await client.get("/api/config")
    assert resp.status_code == 200
    data = resp.json()
    assert "defaultModel" in data
    assert "requireAuth" in data
    # API key must not be exposed
    assert "defaultApiKey" not in data or data.get("defaultApiKey") is None
