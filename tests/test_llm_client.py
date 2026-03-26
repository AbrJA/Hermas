"""Tests for LLM client helpers."""

from hermas.services.llm_client import (
    _is_default_openai,
    _normalize_openai_url,
    _sanitize_base_url,
)


def test_sanitize_base_url():
    assert _sanitize_base_url("https://api.openai.com/") == "https://api.openai.com"
    assert _sanitize_base_url("  https://api.openai.com  ") == "https://api.openai.com"
    assert _sanitize_base_url("https://api.openai.com") == "https://api.openai.com"


def test_normalize_openai_url():
    assert _normalize_openai_url("https://custom.api.com") == "https://custom.api.com/v1"
    assert _normalize_openai_url("https://custom.api.com/v1") == "https://custom.api.com/v1"
    assert _normalize_openai_url("https://custom.api.com/V1") == "https://custom.api.com/V1"


def test_is_default_openai():
    assert _is_default_openai("https://api.openai.com") is True
    assert _is_default_openai("https://api.openai.com/v1") is True
    assert _is_default_openai("https://api.openai.com/") is True
    assert _is_default_openai("https://custom.server.com") is False
