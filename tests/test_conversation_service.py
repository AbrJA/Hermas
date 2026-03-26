"""Tests for conversation service."""

import pytest

from hermas.services import conversation_service


@pytest.mark.asyncio
async def test_save_and_load_conversation(db_session):
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
    ]
    result = await conversation_service.save_conversation(
        db_session, "alice", "conv-1", "gpt-4", messages
    )
    assert result["id"] == "conv-1"
    assert result["title"] == "Hello"
    assert result["model"] == "gpt-4"

    loaded = await conversation_service.load_conversation(db_session, "alice", "conv-1")
    assert loaded is not None
    assert loaded["id"] == "conv-1"
    assert len(loaded["messages"]) == 2
    assert loaded["messages"][0]["role"] == "user"
    assert loaded["messages"][0]["content"] == "Hello"


@pytest.mark.asyncio
async def test_list_conversations(db_session):
    await conversation_service.save_conversation(
        db_session, "alice", "conv-a", "gpt-4", [{"role": "user", "content": "First"}]
    )
    await conversation_service.save_conversation(
        db_session, "alice", "conv-b", "gpt-4", [{"role": "user", "content": "Second"}]
    )

    summaries = await conversation_service.list_conversations(db_session, "alice")
    assert len(summaries) >= 2
    ids = [s["id"] for s in summaries]
    assert "conv-a" in ids
    assert "conv-b" in ids


@pytest.mark.asyncio
async def test_load_nonexistent_conversation(db_session):
    result = await conversation_service.load_conversation(db_session, "alice", "nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_user_isolation(db_session):
    await conversation_service.save_conversation(
        db_session, "alice", "alice-conv", "gpt-4", [{"role": "user", "content": "Alice's msg"}]
    )
    # Bob shouldn't see Alice's conversations
    loaded = await conversation_service.load_conversation(db_session, "bob", "alice-conv")
    assert loaded is None


@pytest.mark.asyncio
async def test_conversation_update(db_session):
    messages1 = [{"role": "user", "content": "Hello"}]
    await conversation_service.save_conversation(db_session, "alice", "conv-upd", "gpt-4", messages1)

    messages2 = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi!"},
        {"role": "user", "content": "How are you?"},
    ]
    await conversation_service.save_conversation(db_session, "alice", "conv-upd", "gpt-4", messages2)

    loaded = await conversation_service.load_conversation(db_session, "alice", "conv-upd")
    assert loaded is not None
    assert len(loaded["messages"]) == 3


@pytest.mark.asyncio
async def test_title_truncation(db_session):
    long_msg = "A" * 200
    await conversation_service.save_conversation(
        db_session, "alice", "conv-long", "gpt-4", [{"role": "user", "content": long_msg}]
    )
    loaded = await conversation_service.load_conversation(db_session, "alice", "conv-long")
    assert loaded is not None
    assert len(loaded["title"]) <= 67  # 64 + "..."


@pytest.mark.asyncio
async def test_safe_user_id():
    from hermas.services.conversation_service import _safe_user_id

    assert _safe_user_id("Alice@Company") == "alice-company"
    assert _safe_user_id("") == "anonymous"
    assert _safe_user_id("valid-user") == "valid-user"
    assert _safe_user_id("  UPPER  ") == "upper"
