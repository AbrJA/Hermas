"""Tests for database module."""

import pytest

from hermas.config import AppConfig
from hermas.database import _db_url, get_session_factory


def test_db_url():
    cfg = AppConfig(_env_file=None, data_dir="test_data")
    url = _db_url(cfg)
    assert "sqlite+aiosqlite" in url
    assert "hermas.db" in url


def test_get_session_factory_when_uninitialized(monkeypatch):
    from hermas import database as db_mod
    monkeypatch.setattr(db_mod, "_session_factory", None)
    with pytest.raises(RuntimeError, match="not initialized"):
        get_session_factory()
