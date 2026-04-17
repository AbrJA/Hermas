"""Tests for dependency injection and middleware."""


import pytest

from hermas.api.dependencies import get_app_config, require_app_token, require_session
from hermas.config import AppConfig


def test_get_app_config(monkeypatch):
    from hermas import config as config_mod
    cfg = AppConfig(_env_file=None, default_api_key="test")
    monkeypatch.setattr(config_mod, "_config", cfg)
    result = get_app_config()
    assert result.default_api_key == "test"


@pytest.mark.asyncio
async def test_require_app_token_auth_disabled(app_config):
    # require_auth=False should pass through
    await require_app_token(app_config, "")


@pytest.mark.asyncio
async def test_require_app_token_auth_enabled_valid():
    cfg = AppConfig(
        _env_file=None,
        require_auth=True,
        app_api_token="valid-token",
    )
    await require_app_token(cfg, "valid-token")


@pytest.mark.asyncio
async def test_require_app_token_auth_enabled_invalid():
    from fastapi import HTTPException

    cfg = AppConfig(
        _env_file=None,
        require_auth=True,
        app_api_token="valid-token",
    )
    with pytest.raises(HTTPException) as exc_info:
        await require_app_token(cfg, "wrong-token")
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_require_app_token_auth_enabled_no_server_token():
    from fastapi import HTTPException

    cfg = AppConfig(
        _env_file=None,
        require_auth=True,
        app_api_token="",
    )
    with pytest.raises(HTTPException) as exc_info:
        await require_app_token(cfg, "some-token")
    assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_require_session_auth_disabled(app_config, db_session):
    result = await require_session(app_config, db_session, authorization="", x_session_token="", x_user_id="alice")
    assert result == "alice"


@pytest.mark.asyncio
async def test_require_session_auth_disabled_anonymous(app_config, db_session):
    result = await require_session(app_config, db_session, authorization="", x_session_token="", x_user_id="")
    assert result == "anonymous"


@pytest.mark.asyncio
async def test_require_session_auth_enabled_valid(db_session):
    from hermas.services import session_service

    cfg = AppConfig(_env_file=None, require_auth=True)
    token = await session_service.create_session(db_session, "bob", 3600)
    result = await require_session(cfg, db_session, authorization="", x_session_token=token, x_user_id="bob")
    assert result == "bob"


@pytest.mark.asyncio
async def test_require_session_auth_enabled_invalid(db_session):
    from fastapi import HTTPException

    cfg = AppConfig(_env_file=None, require_auth=True)
    with pytest.raises(HTTPException) as exc_info:
        await require_session(cfg, db_session, authorization="", x_session_token="invalid-token", x_user_id="bob")
    assert exc_info.value.status_code == 401
