"""Tests for MCP service (server CRUD)."""

import pytest

from hermas.services import mcp_service


@pytest.mark.asyncio
async def test_save_and_list_servers(db_session):
    payload = {
        "name": "Test MCP",
        "url": "http://localhost:8000/mcp",
        "authHeaderName": "Authorization",
        "authHeaderValue": "Bearer secret",
        "enabled": True,
    }
    saved = await mcp_service.save_server(db_session, "alice", payload)
    assert saved["name"] == "Test MCP"
    assert saved["url"] == "http://localhost:8000/mcp"
    assert "id" in saved

    servers = await mcp_service.list_servers(db_session, "alice")
    assert len(servers) >= 1
    assert any(s["name"] == "Test MCP" for s in servers)


@pytest.mark.asyncio
async def test_get_server(db_session):
    saved = await mcp_service.save_server(db_session, "alice", {
        "name": "Get Test",
        "url": "http://localhost:9000/mcp",
    })
    found = await mcp_service.get_server(db_session, "alice", saved["id"])
    assert found is not None
    assert found["name"] == "Get Test"


@pytest.mark.asyncio
async def test_update_server(db_session):
    saved = await mcp_service.save_server(db_session, "alice", {
        "name": "Original",
        "url": "http://localhost:8000/mcp",
    })
    updated = await mcp_service.save_server(db_session, "alice", {
        "id": saved["id"],
        "name": "Updated",
        "url": "http://localhost:8001/mcp",
    })
    assert updated["id"] == saved["id"]
    assert updated["name"] == "Updated"
    assert updated["url"] == "http://localhost:8001/mcp"


@pytest.mark.asyncio
async def test_delete_server(db_session):
    saved = await mcp_service.save_server(db_session, "alice", {
        "name": "ToDelete",
        "url": "http://localhost:8000/mcp",
    })
    deleted = await mcp_service.delete_server(db_session, "alice", saved["id"])
    assert deleted is True

    found = await mcp_service.get_server(db_session, "alice", saved["id"])
    assert found is None


@pytest.mark.asyncio
async def test_delete_nonexistent_server(db_session):
    deleted = await mcp_service.delete_server(db_session, "alice", "nonexistent")
    assert deleted is False


@pytest.mark.asyncio
async def test_user_isolation(db_session):
    saved = await mcp_service.save_server(db_session, "alice", {
        "name": "Alice's Server",
        "url": "http://localhost:8000/mcp",
    })
    servers = await mcp_service.list_servers(db_session, "bob")
    assert not any(s["id"] == saved["id"] for s in servers)
