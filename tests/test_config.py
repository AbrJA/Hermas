"""Tests for AppConfig."""


from solomon.config import AppConfig


def test_defaults():
    cfg = AppConfig(
        _env_file=None,
        default_api_key="",
    )
    assert cfg.host == "0.0.0.0"
    assert cfg.port == 8080
    assert cfg.default_model == "gpt-4o-mini"
    assert cfg.require_auth is False
    assert cfg.session_ttl_seconds == 86400
    assert cfg.cors_origin == "*"


def test_env_override(monkeypatch):
    monkeypatch.setenv("SOLOMON_PORT", "9090")
    monkeypatch.setenv("SOLOMON_DEFAULT_MODEL", "o4-mini")
    monkeypatch.setenv("SOLOMON_REQUIRE_AUTH", "true")
    monkeypatch.setenv("SOLOMON_SESSION_TTL_SECONDS", "7200")
    cfg = AppConfig(_env_file=None)
    assert cfg.port == 9090
    assert cfg.default_model == "o4-mini"
    assert cfg.require_auth is True
    assert cfg.session_ttl_seconds == 7200
