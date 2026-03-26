"""Skill routing service – LLM-based smart skill selection."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from solomon.config import AppConfig
from solomon.services import llm_client, skill_service


def _bool_value(value, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in ("1", "true", "yes", "on"):
            return True
        if normalized in ("0", "false", "no", "off"):
            return False
    return default


def _latest_user_query(messages: list[dict]) -> str:
    for msg in reversed(messages):
        if str(msg.get("role", "")).lower().strip() == "user":
            content = str(msg.get("content", "")).strip()
            if content:
                return content
    return ""


class _SkillProxy:
    """Lightweight skill proxy for the LLM routing call."""

    __slots__ = ("description", "id", "name")

    def __init__(self, skill: dict):
        self.id = skill["id"]
        self.name = skill["name"]
        self.description = skill["description"]


async def resolve_skill_ids(
    payload: dict,
    cfg: AppConfig,
    messages: list[dict],
    api_key: str,
    base_url: str,
    model: str,
    db: AsyncSession,
) -> list[str]:
    skill_ids_raw = payload.get("selectedSkillIds", [])
    candidate_ids: list[str] = [str(x) for x in skill_ids_raw] if isinstance(skill_ids_raw, list) else []
    if not candidate_ids:
        return []

    auto_routing = _bool_value(payload.get("autoSkillRouting", True), True)
    if not auto_routing:
        return candidate_ids

    all_skills = await skill_service.list_skills(db)
    id_set = set(candidate_ids)
    candidates = [s for s in all_skills if s["id"] in id_set]
    if not candidates:
        return []

    query = _latest_user_query(messages)
    if not query.strip():
        return []

    proxies = [_SkillProxy(s) for s in candidates]
    chosen = await llm_client.route_skill(
        base_url=base_url,
        api_key=api_key,
        model=model,
        query=query,
        skills=proxies,
        timeout_seconds=min(cfg.request_timeout_seconds, 10),
    )
    return [chosen] if chosen else []
