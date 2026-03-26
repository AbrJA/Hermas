"""Tests for chat service helpers."""

import pytest

from solomon.services.chat_service import (
    _conversation_id,
    _extract_tool_call,
    _format_tool_result,
    _looks_like_tool_intent,
    _normalize_messages,
)


def test_normalize_messages():
    raw = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
    ]
    result = _normalize_messages(raw)
    assert len(result) == 2
    assert result[0]["role"] == "user"


def test_normalize_messages_strips_empty():
    raw = [
        {"role": "user", "content": "Hello"},
        {"role": "user", "content": "  "},
    ]
    result = _normalize_messages(raw)
    assert len(result) == 1


def test_normalize_messages_empty_raises():
    with pytest.raises(ValueError, match="cannot be empty"):
        _normalize_messages([])


def test_normalize_messages_not_list_raises():
    with pytest.raises(ValueError, match="must be an array"):
        _normalize_messages("not a list")


def test_conversation_id_existing():
    assert _conversation_id({"conversationId": "abc-123"}) == "abc-123"


def test_conversation_id_generated():
    cid = _conversation_id({})
    assert len(cid) == 36  # UUID


def test_extract_tool_call_valid():
    content = '<tool_call>\n{"server": "mysql", "tool": "run_query", "arguments": {"query": "SELECT 1"}}\n</tool_call>'
    result = _extract_tool_call(content)
    assert result is not None
    assert result["server"] == "mysql"
    assert result["tool"] == "run_query"
    assert result["arguments"]["query"] == "SELECT 1"


def test_extract_tool_call_no_match():
    assert _extract_tool_call("Just normal text") is None


def test_extract_tool_call_missing_fields():
    content = '<tool_call>\n{"server": "mysql"}\n</tool_call>'
    assert _extract_tool_call(content) is None


def test_looks_like_tool_intent_true():
    assert _looks_like_tool_intent("I will check the database for that.") is True
    assert _looks_like_tool_intent("Let me query the table.") is True


def test_looks_like_tool_intent_false():
    assert _looks_like_tool_intent("Here are your results.") is False
    assert _looks_like_tool_intent("The answer is 42.") is False


def test_format_tool_result_dict_with_content():
    result = {"content": [{"type": "text", "text": "Hello World"}]}
    assert _format_tool_result(result) == "Hello World"


def test_format_tool_result_plain_dict():
    result = {"data": [1, 2, 3]}
    formatted = _format_tool_result(result)
    assert "1" in formatted
    assert "2" in formatted


def test_format_tool_result_string():
    assert '"hello"' in _format_tool_result("hello")
