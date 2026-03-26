"""Tests for prompt builder."""

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


def test_build_mcp_server_configs_from_list():
    payload = {
        "mcpServers": [
            {"name": "server-1", "url": "http://localhost:8000/mcp"},
            {"name": "server-2", "url": "http://localhost:9000/mcp", "authHeaderName": "Authorization", "authHeaderValue": "Bearer x"},
        ]
    }
    configs = build_mcp_server_configs(payload)
    assert len(configs) == 2
    assert "server-1" in configs
    assert "server-2" in configs
    assert configs["server-2"].auth_header_name == "Authorization"


def test_build_mcp_server_configs_from_single():
    payload = {
        "mcpServer": {"url": "http://localhost:8000/mcp"},
    }
    configs = build_mcp_server_configs(payload)
    assert len(configs) == 1


def test_build_mcp_server_configs_empty():
    configs = build_mcp_server_configs({})
    assert len(configs) == 0


def test_build_mcp_server_configs_invalid_skipped():
    payload = {"mcpServers": [{"name": "no-url"}, {"url": "http://valid.com"}]}
    configs = build_mcp_server_configs(payload)
    assert len(configs) == 1
