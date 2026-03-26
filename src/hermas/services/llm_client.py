"""LLM client wrapping the OpenAI Python SDK.

Supports OpenAI and any OpenAI-compatible provider via custom base_url.
"""

from __future__ import annotations

import re
import time

import structlog
from openai import AsyncOpenAI
from openai import NotFoundError

from hermas.schemas.common import LLMResult, LLMUsage

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# URL helpers (ported from Julia LLMClient.jl)
# ---------------------------------------------------------------------------


def _sanitize_base_url(base_url: str) -> str:
    cleaned = base_url.strip().rstrip("/")
    return cleaned


def _normalize_openai_url(base_url: str) -> str:
    clean = _sanitize_base_url(base_url)
    lower = clean.lower()
    # Azure-style endpoints must not be rewritten to include /v1.
    if "/openai/deployments/" in lower or "openai.azure.com" in lower:
        return clean
    if lower.endswith("/v1"):
        return clean
    return f"{clean}/v1"


def _is_default_openai(base_url: str) -> bool:
    clean = _sanitize_base_url(base_url).lower()
    return clean in ("https://api.openai.com", "https://api.openai.com/v1")


# ---------------------------------------------------------------------------
# Client cache – one AsyncOpenAI instance per (base_url, api_key)
# ---------------------------------------------------------------------------

_clients: dict[tuple[str, str], AsyncOpenAI] = {}


def _get_client(base_url: str, api_key: str) -> AsyncOpenAI:
    if not api_key.strip():
        raise ValueError("No API key provided and HERMAS_DEFAULT_API_KEY is not set")

    url = _normalize_openai_url(base_url)
    key = (url, api_key)
    client = _clients.get(key)
    if client is None:
        client = AsyncOpenAI(base_url=url, api_key=api_key)
        _clients[key] = client
    return client


# ---------------------------------------------------------------------------
# Parse usage from OpenAI response
# ---------------------------------------------------------------------------


def _parse_usage(usage) -> LLMUsage:
    if usage is None:
        return LLMUsage()
    return LLMUsage(
        input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
        output_tokens=getattr(usage, "completion_tokens", 0) or 0,
    )


# ---------------------------------------------------------------------------
# Chat completion
# ---------------------------------------------------------------------------


async def chat_completion(
    *,
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict],
    system_prompt: str = "",
    temperature: float = 0.2,
    max_tokens: int = 1200,
    timeout_seconds: int = 30,
) -> LLMResult:
    client = _get_client(base_url, api_key)

    oai_messages: list[dict] = []
    if system_prompt.strip():
        oai_messages.append({"role": "system", "content": system_prompt.strip()})
    for msg in messages:
        role = str(msg.get("role", "user")).lower().strip()
        content = str(msg.get("content", "")).strip()
        if not content:
            continue
        if role not in ("user", "assistant", "system"):
            role = "user"
        oai_messages.append({"role": role, "content": content})

    start = time.monotonic()
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=oai_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout_seconds,
        )
    except NotFoundError as exc:
        resolved_url = _normalize_openai_url(base_url)
        logger.warning(
            "llm_not_found",
            status_code=404,
            base_url=resolved_url,
            model=model,
            hint="Check HERMAS_LLM_BASE_URL and HERMAS_DEFAULT_MODEL for provider compatibility",
        )
        raise RuntimeError(
            f"LLM endpoint/model not found (404). base_url='{resolved_url}', model='{model}'. "
            "Check HERMAS_LLM_BASE_URL and HERMAS_DEFAULT_MODEL."
        ) from exc
    elapsed = time.monotonic() - start

    content = response.choices[0].message.content or "" if response.choices else ""
    usage = _parse_usage(response.usage)
    usage.elapsed = elapsed
    usage.model_id = response.model or model

    return LLMResult(content=content, model=response.model or model, usage=usage)


# ---------------------------------------------------------------------------
# Streaming chat completion – yields content deltas
# ---------------------------------------------------------------------------


async def chat_completion_stream(
    *,
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict],
    system_prompt: str = "",
    temperature: float = 0.2,
    max_tokens: int = 1200,
    timeout_seconds: int = 30,
):
    """Async generator that yields content string chunks."""
    client = _get_client(base_url, api_key)

    oai_messages: list[dict] = []
    if system_prompt.strip():
        oai_messages.append({"role": "system", "content": system_prompt.strip()})
    for msg in messages:
        role = str(msg.get("role", "user")).lower().strip()
        content = str(msg.get("content", "")).strip()
        if not content:
            continue
        if role not in ("user", "assistant", "system"):
            role = "user"
        oai_messages.append({"role": role, "content": content})

    try:
        stream = await client.chat.completions.create(
            model=model,
            messages=oai_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout_seconds,
            stream=True,
        )
    except NotFoundError as exc:
        resolved_url = _normalize_openai_url(base_url)
        logger.warning(
            "llm_not_found",
            status_code=404,
            base_url=resolved_url,
            model=model,
            hint="Check HERMAS_LLM_BASE_URL and HERMAS_DEFAULT_MODEL for provider compatibility",
        )
        raise RuntimeError(
            f"LLM endpoint/model not found (404). base_url='{resolved_url}', model='{model}'. "
            "Check HERMAS_LLM_BASE_URL and HERMAS_DEFAULT_MODEL."
        ) from exc
    async for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


# ---------------------------------------------------------------------------
# Skill routing – deterministic LLM call to pick a skill
# ---------------------------------------------------------------------------


async def route_skill(
    *,
    base_url: str,
    api_key: str,
    model: str,
    query: str,
    skills: list,
    timeout_seconds: int = 10,
) -> str:
    if not skills or not query.strip():
        return ""

    valid_ids = {s.id for s in skills}
    skill_lines = "\n".join(f"{s.id}: {s.name} - {s.description}" for s in skills)

    routing_messages = [
        {
            "role": "user",
            "content": (
                f"Current user request (this turn only): {query}\n\n"
                f"Available skills:\n{skill_lines}\n\n"
                "Select a skill ID only if the current request clearly requires that skill behavior. "
                "If not clearly required, reply 'none'. Reply with ONLY the skill ID, or 'none'."
            ),
        }
    ]

    try:
        result = await chat_completion(
            base_url=base_url,
            api_key=api_key,
            model=model,
            messages=routing_messages,
            system_prompt=(
                "You are a strict skill router. Decide based only on the current user request. "
                "Do not infer from previous turns. Return 'none' unless a listed skill is explicitly "
                "needed by the current request. Reply with only the ID or 'none' and nothing else."
            ),
            temperature=0.0,
            max_tokens=20,
            timeout_seconds=timeout_seconds,
        )
    except Exception as exc:
        logger.warning("skill_routing_failed", error=str(exc))
        return ""

    chosen = re.sub(r"[\"'.,!;:\n]", "", result.content).strip().lower()
    return chosen if chosen in valid_ids else ""
