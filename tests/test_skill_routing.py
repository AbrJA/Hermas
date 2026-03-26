"""Tests for skill routing service."""

from solomon.services.skill_routing_service import _bool_value, _latest_user_query


def test_latest_user_query():
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi!"},
        {"role": "user", "content": "What is Python?"},
    ]
    assert _latest_user_query(messages) == "What is Python?"


def test_latest_user_query_no_user():
    messages = [{"role": "assistant", "content": "Hello"}]
    assert _latest_user_query(messages) == ""


def test_latest_user_query_empty():
    assert _latest_user_query([]) == ""


def test_bool_value():
    assert _bool_value(True, False) is True
    assert _bool_value(False, True) is False
    assert _bool_value("true", False) is True
    assert _bool_value("false", True) is False
    assert _bool_value(None, True) is True
