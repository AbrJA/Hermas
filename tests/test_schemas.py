"""Tests for schemas to ensure coverage."""

from hermas.schemas.chat import ChatRequest, ChatResponse
from hermas.schemas.common import LLMResult, LLMUsage
from hermas.schemas.conversation import ConversationDetail, ConversationSummary
from hermas.schemas.mcp import MCPCallToolRequest, MCPServerCreate, MCPToolRequest
from hermas.schemas.session import SessionCreateRequest, SessionCreateResponse
from hermas.schemas.skill import SkillCreateRequest


def test_chat_request():
    req = ChatRequest(messages=[{"role": "user", "content": "Hello"}])
    assert req.temperature == 0.2
    assert req.maxTokens == 1200
    assert req.autoSkillRouting is True
    assert req.mcpServerIds == []
    assert req.mcpServerId == ""


def test_chat_request_with_mcp():
    req = ChatRequest(
        messages=[{"role": "user", "content": "Hi"}],
        mcpServerId="server-1",
        model="gpt-4",
    )
    assert req.mcpServerId == "server-1"
    assert req.model == "gpt-4"


def test_chat_response():
    resp = ChatResponse(
        conversationId="abc",
        message={"role": "assistant", "content": "Hi"},
        model="gpt-4",
        usage={"inputTokens": 10, "outputTokens": 20},
        appliedSkillIds=["skill-1"],
    )
    assert resp.conversationId == "abc"
    assert resp.appliedSkillIds == ["skill-1"]


def test_conversation_summary():
    s = ConversationSummary(id="c1", title="Hello", updatedAt="2024-01-01T00:00:00", model="gpt-4")
    assert s.id == "c1"


def test_conversation_detail():
    d = ConversationDetail(
        id="c1",
        title="Hello",
        model="gpt-4",
        createdAt="2024-01-01T00:00:00",
        updatedAt="2024-01-01T00:00:00",
        messages=[],
    )
    assert d.messages == []


def test_llm_usage():
    u = LLMUsage(input_tokens=10, output_tokens=20, elapsed=1.5, model_id="gpt-4")
    d = u.to_camel_dict()
    assert d["inputTokens"] == 10
    assert d["outputTokens"] == 20
    assert d["elapsed"] == 1.5
    assert d["modelId"] == "gpt-4"


def test_llm_result():
    r = LLMResult(content="Hello", model="gpt-4", usage=LLMUsage())
    assert r.content == "Hello"


def test_session_schemas():
    req = SessionCreateRequest(userId="alice")
    assert req.userId == "alice"
    resp = SessionCreateResponse(sessionToken="abc", userId="alice", expiresAt=1234567890)
    assert resp.sessionToken == "abc"


def test_skill_create_request():
    req = SkillCreateRequest(name="Test", content="Do stuff")
    assert req.name == "Test"
    assert req.description == "No description provided"
    assert req.id == ""


def test_mcp_server_create():
    req = MCPServerCreate(name="Test", url="http://localhost:8000/mcp")
    assert req.enabled is True
    assert req.timeoutSeconds == 15


def test_mcp_tool_request():
    req = MCPToolRequest(serverId="server-1")
    assert req.serverId == "server-1"


def test_mcp_call_tool_request():
    req = MCPCallToolRequest(
        serverId="server-1",
        toolName="run_query",
        arguments={"query": "SELECT 1"},
    )
    assert req.toolName == "run_query"
