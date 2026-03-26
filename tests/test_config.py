"""Tests for AppConfig."""


from hermas.config import AppConfig


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
    monkeypatch.setenv("HERMAS_PORT", "9090")
    monkeypatch.setenv("HERMAS_DEFAULT_MODEL", "o4-mini")
    monkeypatch.setenv("HERMAS_REQUIRE_AUTH", "true")
    monkeypatch.setenv("HERMAS_SESSION_TTL_SECONDS", "7200")
    cfg = AppConfig(_env_file=None)
    assert cfg.port == 9090
    assert cfg.default_model == "o4-mini"
    assert cfg.require_auth is True
    assert cfg.session_ttl_seconds == 7200
