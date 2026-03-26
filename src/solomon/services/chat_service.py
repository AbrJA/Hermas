"""Chat service – orchestrates LLM calls, tool loops, and conversation persistence.

Supports both synchronous (complete_chat) and true SSE streaming (complete_chat_stream).
"""

from __future__ import annotations

import json
import re
import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from solomon.config import AppConfig
from solomon.schemas.common import LLMUsage
from solomon.services import conversation_service, llm_client, prompt_builder, stream_formatter
from solomon.services import mcp_client as mcp_client_mod
from solomon.services.mcp_client import MCPServerConfig

logger = structlog.get_logger()

_TOOL_CALL_PATTERN = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)
_MAX_TOOL_ITERATIONS = 8
_MAX_TOOL_RESULT_LENGTH = 8000

_INTENT_PATTERNS = [
    re.compile(
        r"(?:I will|I'll|Let me|I need to|I should|I'm going to|Next,? I will|I want to)\s+"
        r"(?:check|query|look|get|list|run|fetch|retrieve|examine|inspect|use|call)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:check|query|look at|get|retrieve|examine|inspect) the (?:schema|table|database|data)",
        re.IGNORECASE,
    ),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalize_messages(raw_messages) -> list[dict]:
    if not isinstance(raw_messages, list):
        raise ValueError("messages must be an array")
    normalized: list[dict] = []
    for item in raw_messages:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "user"))
        content = str(item.get("content", "")).strip()
        if not content:
            continue
        normalized.append({"role": role, "content": content})
    if not normalized:
        raise ValueError("messages cannot be empty")
    return normalized


def _conversation_id(payload: dict) -> str:
    incoming = str(payload.get("conversationId", "")).strip()
    return incoming if incoming else str(uuid.uuid4())


def _extract_tool_call(content: str) -> dict | None:
    m = _TOOL_CALL_PATTERN.search(content)
    if not m:
        return None
    try:
        parsed = json.loads(m.group(1))
        if not isinstance(parsed, dict):
            return None
        server = str(parsed.get("server", ""))
        tool = str(parsed.get("tool", ""))
        arguments = parsed.get("arguments", {})
        if not isinstance(arguments, dict):
            arguments = {}
        if not server or not tool:
            return None
        return {"server": server, "tool": tool, "arguments": arguments}
    except (json.JSONDecodeError, KeyError):
        return None


def _looks_like_tool_intent(content: str) -> bool:
    return any(p.search(content) for p in _INTENT_PATTERNS)


def _format_tool_result(result) -> str:
    if isinstance(result, dict):
        content = result.get("content")
        if isinstance(content, list):
            texts = [str(item.get("text", "")) for item in content if isinstance(item, dict) and item.get("type") == "text"]
            if texts:
                return "\n".join(texts)
    return json.dumps(result, default=str)


async def _execute_tool(tool_call: dict, mcp_configs: dict[str, MCPServerConfig]) -> str:
    config = mcp_configs.get(tool_call["server"])
    if config is None:
        return f"Error: Unknown MCP server '{tool_call['server']}'"
    try:
        result = await mcp_client_mod.call_tool(config, tool_call["tool"], tool_call["arguments"])
        raw = _format_tool_result(result)
        if len(raw) > _MAX_TOOL_RESULT_LENGTH:
            return raw[:_MAX_TOOL_RESULT_LENGTH] + "\n... (truncated)"
        return raw
    except Exception as exc:
        return f"Error calling tool '{tool_call['tool']}': {exc}"


# ---------------------------------------------------------------------------
# Chat context builder
# ---------------------------------------------------------------------------


async def _chat_context(payload: dict, cfg: AppConfig, db: AsyncSession) -> dict:
    messages = _normalize_messages(payload.get("messages", []))
    model = str(payload.get("model", "")) or cfg.default_model
    base_url = str(payload.get("baseUrl", "")) or cfg.llm_base_url
    user_api_key = str(payload.get("apiKey", "")).strip()
    api_key = user_api_key if user_api_key else cfg.default_api_key
    temperature = float(payload.get("temperature", 0.2))
    max_tokens = int(payload.get("maxTokens", 1200))

    system_prompt, applied_skill_ids = await prompt_builder.build_system_prompt(
        payload, cfg, messages, api_key, base_url, model, db
    )
    mcp_configs = prompt_builder.build_mcp_server_configs(payload)
    system_prompt = await prompt_builder.append_mcp_context(system_prompt, mcp_configs, db)

    return {
        "messages": messages,
        "model": model,
        "base_url": base_url,
        "api_key": api_key,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "system_prompt": system_prompt,
        "applied_skill_ids": applied_skill_ids,
        "mcp_configs": mcp_configs,
    }


# ---------------------------------------------------------------------------
# Tool-calling loop (non-streaming)
# ---------------------------------------------------------------------------


async def _chat_with_tools(
    cfg: AppConfig,
    ctx: dict,
    *,
    on_tool_start=None,
    on_tool_done=None,
) -> str:
    if not ctx["mcp_configs"]:
        result = await llm_client.chat_completion(
            base_url=ctx["base_url"],
            api_key=ctx["api_key"],
            model=ctx["model"],
            messages=ctx["messages"],
            system_prompt=ctx["system_prompt"],
            temperature=ctx["temperature"],
            max_tokens=ctx["max_tokens"],
            timeout_seconds=cfg.request_timeout_seconds,
        )
        return result.content

    messages = list(ctx["messages"])
    retried_intent = False

    for iteration in range(1, _MAX_TOOL_ITERATIONS + 1):
        result = await llm_client.chat_completion(
            base_url=ctx["base_url"],
            api_key=ctx["api_key"],
            model=ctx["model"],
            messages=messages,
            system_prompt=ctx["system_prompt"],
            temperature=0.0,
            max_tokens=max(ctx["max_tokens"], 2000),
            timeout_seconds=cfg.request_timeout_seconds,
        )

        content = result.content
        tool_call = _extract_tool_call(content)

        if tool_call is None:
            if not retried_intent and _looks_like_tool_intent(content):
                logger.info("tool_intent_nudge", iteration=iteration)
                retried_intent = True
                messages.append({"role": "assistant", "content": content})
                messages.append({
                    "role": "user",
                    "content": (
                        "Do NOT describe what you will do. Instead, call the tool NOW using the exact "
                        "<tool_call> format. Your entire response must be ONLY the <tool_call> block, nothing else."
                    ),
                })
                continue
            return content

        retried_intent = False
        logger.info("mcp_tool_call", iteration=iteration, server=tool_call["server"], tool=tool_call["tool"])

        if on_tool_start:
            on_tool_start(iteration, tool_call["server"], tool_call["tool"])

        tool_result = await _execute_tool(tool_call, ctx["mcp_configs"])
        logger.info("mcp_tool_result", length=len(tool_result))

        if on_tool_done:
            on_tool_done(iteration, tool_call["server"], tool_call["tool"], len(tool_result))

        messages.append({"role": "assistant", "content": content})
        messages.append({
            "role": "user",
            "content": (
                f"[Tool Result for {tool_call['tool']}]:\n{tool_result}\n\n"
                "If you need more data, call another tool using the <tool_call> format. "
                "Otherwise, present the final answer to the user in a clear, readable way."
            ),
        })

    return "I attempted to use tools but reached the maximum number of iterations. Please try a more specific request."


# ---------------------------------------------------------------------------
# Public API – non-streaming
# ---------------------------------------------------------------------------


async def complete_chat(cfg: AppConfig, user_id: str, payload: dict, db: AsyncSession) -> dict:
    conversation_id = _conversation_id(payload)
    ctx = await _chat_context(payload, cfg, db)

    content = await _chat_with_tools(cfg, ctx)

    # Save conversation
    final_messages = list(ctx["messages"]) + [{"role": "assistant", "content": content}]
    await conversation_service.save_conversation(db, user_id, conversation_id, ctx["model"], final_messages)

    return {
        "conversationId": conversation_id,
        "content": content,
        "model": ctx["model"],
        "usage": LLMUsage().to_camel_dict(),
        "appliedSkillIds": ctx["applied_skill_ids"],
    }


# ---------------------------------------------------------------------------
# Public API – true SSE streaming
# ---------------------------------------------------------------------------


async def complete_chat_stream(cfg: AppConfig, user_id: str, payload: dict, db: AsyncSession):
    """Async generator yielding SSE event strings."""
    conversation_id = _conversation_id(payload)
    ctx = await _chat_context(payload, cfg, db)

    # Start event
    yield stream_formatter.sse_event("start", {
        "conversationId": conversation_id,
        "model": ctx["model"],
        "appliedSkillIds": ctx["applied_skill_ids"],
    })

    # If MCP tools are configured, run tool loop first (non-streaming)
    if ctx["mcp_configs"]:
        tool_events: list[str] = []

        def on_tool_start(iteration, server, tool):
            tool_events.append(stream_formatter.sse_event("tool_start", {
                "iteration": iteration, "server": server, "tool": tool,
            }))

        def on_tool_done(iteration, server, tool, result_length):
            tool_events.append(stream_formatter.sse_event("tool_done", {
                "iteration": iteration, "server": server, "tool": tool, "resultLength": result_length,
            }))

        try:
            content = await _chat_with_tools(cfg, ctx, on_tool_start=on_tool_start, on_tool_done=on_tool_done)
        except Exception as exc:
            logger.warning("chat_completion_failed", error=str(exc))
            content = "I could not complete the request right now. Please retry in a few seconds."

        # Yield buffered tool events
        for ev in tool_events:
            yield ev

        # Stream the final content token by token (simulated from the buffered response)
        content = content.strip() or "(Empty response)"
        yield stream_formatter.sse_event("token", {"delta": content})
    else:
        # True token-by-token streaming (no tools)
        collected: list[str] = []
        try:
            async for delta in llm_client.chat_completion_stream(
                base_url=ctx["base_url"],
                api_key=ctx["api_key"],
                model=ctx["model"],
                messages=ctx["messages"],
                system_prompt=ctx["system_prompt"],
                temperature=ctx["temperature"],
                max_tokens=ctx["max_tokens"],
                timeout_seconds=cfg.request_timeout_seconds,
            ):
                collected.append(delta)
                yield stream_formatter.sse_event("token", {"delta": delta})
        except Exception as exc:
            logger.warning("stream_failed", error=str(exc))
            if not collected:
                yield stream_formatter.sse_event("token", {"delta": "I could not complete the request right now."})
                collected.append("I could not complete the request right now.")

        content = "".join(collected).strip() or "(Empty response)"

    # Save conversation
    final_messages = list(ctx["messages"]) + [{"role": "assistant", "content": content}]
    await conversation_service.save_conversation(db, user_id, conversation_id, ctx["model"], final_messages)

    # Done event
    yield stream_formatter.sse_event("done", {
        "conversationId": conversation_id,
        "content": content,
        "appliedSkillIds": ctx["applied_skill_ids"],
    })
