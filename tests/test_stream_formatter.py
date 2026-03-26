"""Tests for stream formatter."""

import json

from solomon.services.stream_formatter import sse_event


def test_sse_event_format():
    result = sse_event("start", {"conversationId": "abc", "model": "gpt-4"})
    assert result.startswith("event: start\n")
    assert "data: " in result
    assert result.endswith("\n\n")

    # Parse the data portion
    data_line = result.split("data: ")[1].strip()
    parsed = json.loads(data_line)
    assert parsed["conversationId"] == "abc"
    assert parsed["model"] == "gpt-4"


def test_sse_event_token():
    result = sse_event("token", {"delta": "Hello"})
    assert "event: token" in result
    data_line = result.split("data: ")[1].strip()
    parsed = json.loads(data_line)
    assert parsed["delta"] == "Hello"
