"""Tests for prompt builder."""

import pytest

from hermas.services import mcp_service
from hermas.services.prompt_builder import _bool_value, build_mcp_server_configs


def test_bool_value_true_variants():
    assert _bool_value(True, False) is True
    assert _bool_value("true", False) is True
    assert _bool_value("1", False) is True
    assert _bool_value("yes", False) is True
    assert _bool_value("on", False) is True
    assert _bool_value(1, False) is True


def test_bool_value_false_variants():
    assert _bool_value(False, True) is False
    assert _bool_value("false", True) is False
    assert _bool_value("0", True) is False
    assert _bool_value("no", True) is False
    assert _bool_value("off", True) is False
    assert _bool_value(0, True) is False


def test_bool_value_default():
    assert _bool_value("unknown", True) is True
    assert _bool_value(None, False) is False


@pytest.mark.asyncio
async def test_build_mcp_server_configs_from_list(db_session):
    await mcp_service.save_server(
        db_session,
        "alice",
        {"id": "srv-1", "name": "server-1", "url": "http://localhost:8000/mcp"},
    )
    await mcp_service.save_server(
        db_session,
        "alice",
        {
            "id": "srv-2",
            "name": "server-2",
            "url": "http://localhost:9000/mcp",
            "authHeaderName": "Authorization",
            "authHeaderValue": "Bearer x",
        },
    )
    payload = {"mcpServerIds": ["srv-1", "srv-2"]}
    configs = await build_mcp_server_configs(payload, "alice", db_session)
    assert len(configs) == 2
    assert "server-1" in configs
    assert "server-2" in configs
    assert configs["server-2"].auth_header_name == "Authorization"


@pytest.mark.asyncio
async def test_build_mcp_server_configs_from_single(db_session):
    await mcp_service.save_server(
        db_session,
        "alice",
        {"id": "srv-1", "name": "single", "url": "http://localhost:8000/mcp"},
    )
    payload = {"mcpServerId": "srv-1"}
    configs = await build_mcp_server_configs(payload, "alice", db_session)
    assert len(configs) == 1


@pytest.mark.asyncio
async def test_build_mcp_server_configs_empty(db_session):
    configs = await build_mcp_server_configs({}, "alice", db_session)
    assert len(configs) == 0


@pytest.mark.asyncio
async def test_build_mcp_server_configs_invalid_skipped(db_session):
    payload = {"mcpServerIds": ["missing"]}
    configs = await build_mcp_server_configs(payload, "alice", db_session)
    assert len(configs) == 0

    await mcp_service.save_server(
        db_session,
        "alice",
        {"id": "valid", "name": "valid", "url": "http://valid.com"},
    )
    payload = {"mcpServerIds": ["missing", "valid"]}
    configs = await build_mcp_server_configs(payload, "alice", db_session)
    assert len(configs) == 1
