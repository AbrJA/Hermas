"""Tests for MCP API endpoints."""

import pytest


@pytest.mark.asyncio
async def test_list_servers(client):
    resp = await client.get("/api/mcp/servers")
    assert resp.status_code == 200
    data = resp.json()
    assert "servers" in data
    assert isinstance(data["servers"], list)


@pytest.mark.asyncio
async def test_save_and_list_servers(client):
    resp = await client.post(
        "/api/mcp/servers",
        json={
            "name": "Test Server",
            "url": "http://localhost:8000/mcp",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    server = data["server"]
    assert server["name"] == "Test Server"
    server_id = server["id"]

    resp2 = await client.get("/api/mcp/servers")
    servers = resp2.json()["servers"]
    assert any(s["id"] == server_id for s in servers)


@pytest.mark.asyncio
async def test_delete_server(client):
    resp = await client.post(
        "/api/mcp/servers",
        json={"name": "Delete Me", "url": "http://localhost:8000/mcp"},
    )
    server_id = resp.json()["server"]["id"]

    resp2 = await client.delete(f"/api/mcp/servers/{server_id}")
    assert resp2.status_code == 200

    # Confirm deleted
    resp3 = await client.get("/api/mcp/servers")
    servers = resp3.json()["servers"]
    assert not any(s["id"] == server_id for s in servers)
