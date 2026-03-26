"""Prompt builder – assembles system prompt with skills and MCP context."""

from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from solomon.config import AppConfig
from solomon.services import mcp_client, skill_routing_service, skill_service
from solomon.services.mcp_client import MCPServerConfig

logger = structlog.get_logger()


def _bool_value(value, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        n = value.strip().lower()
        if n in ("1", "true", "yes", "on"):
            return True
        if n in ("0", "false", "no", "off"):
            return False
    return default


# ---------------------------------------------------------------------------
# Build skill context (ported from Julia SkillContextBuilder.jl)
# ---------------------------------------------------------------------------


async def _build_skill_context(skill_ids: list[str], db: AsyncSession) -> str:
    if not skill_ids:
        return ""
    chunks: list[str] = []
    for sid in skill_ids:
        skill = await skill_service.get_skill(db, sid)
        if skill:
            chunks.append(f"# Skill: {skill['name']}\n{skill['content']}")
    return "\n\n---\n\n".join(chunks) if chunks else ""


# ---------------------------------------------------------------------------
# System prompt assembly
# ---------------------------------------------------------------------------


async def build_system_prompt(
    payload: dict,
    cfg: AppConfig,
    messages: list[dict],
    api_key: str,
    base_url: str,
    model: str,
    db: AsyncSession,
) -> tuple[str, list[str]]:
    custom = str(payload.get("systemPrompt", ""))
    resolved_skill_ids = await skill_routing_service.resolve_skill_ids(
        payload, cfg, messages, api_key, base_url, model, db
    )
    skill_context = await _build_skill_context(resolved_skill_ids, db)

    segments: list[str] = [cfg.system_prompt]
    if custom.strip():
        segments.append(custom)

    if skill_context.strip():
        segments.append(
            "Optional skills are transient. Apply the following skill instructions only to this response. "
            "Do not carry their format, persona, or constraints into later turns unless they are selected "
            "again or the user explicitly asks for them.\n\n" + skill_context
        )
    else:
        segments.append(
            "No optional skill applies to this response. Answer normally using the base assistant behavior. "
            "Ignore formatting, output structure, or persona patterns from earlier assistant turns unless "
            "the current user message explicitly asks for them. Do not return JSON, schemas, or key-value "
            "objects unless the current user message explicitly requests JSON. Use plain natural language "
            "by default."
        )

    return "\n\n".join(segments), resolved_skill_ids


# ---------------------------------------------------------------------------
# MCP server config parsing
# ---------------------------------------------------------------------------


def build_mcp_server_configs(payload: dict) -> dict[str, MCPServerConfig]:
    raw_servers: list = []
    mcp_servers_raw = payload.get("mcpServers")
    if isinstance(mcp_servers_raw, list):
        raw_servers.extend(mcp_servers_raw)
    single = payload.get("mcpServer")
    if isinstance(single, dict):
        raw_servers.append(single)

    configs: dict[str, MCPServerConfig] = {}
    for raw in raw_servers:
        if not isinstance(raw, dict) or "url" not in raw:
            continue
        name = str(raw.get("name", raw.get("url", "mcp")))
        try:
            configs[name] = MCPServerConfig(
                url=str(raw["url"]),
                auth_header_name=str(raw.get("authHeaderName", "")),
                auth_header_value=str(raw.get("authHeaderValue", "")),
                timeout_seconds=int(raw.get("timeoutSeconds", 30)),
            )
        except Exception as exc:
            logger.warning("mcp_config_failed", server=name, error=str(exc))

    return configs


# ---------------------------------------------------------------------------
# MCP tool discovery + context injection
# ---------------------------------------------------------------------------


async def _discover_tools(mcp_configs: dict[str, MCPServerConfig]) -> str:
    sections: list[str] = []
    for name, config in mcp_configs.items():
        try:
            tools = await mcp_client.list_tools(config)
            if not tools:
                continue
            lines: list[str] = []
            for tool in tools:
                tool_name = str(tool.get("name", ""))
                tool_desc = str(tool.get("description", ""))
                schema = tool.get("inputSchema")
                args_info = ""
                if isinstance(schema, dict):
                    props = schema.get("properties")
                    if isinstance(props, dict):
                        args_info = " (args: " + ", ".join(props.keys()) + ")"
                lines.append(f"  - {tool_name}: {tool_desc}{args_info}")
            sections.append(f'Server "{name}":\n' + "\n".join(lines))
        except Exception as exc:
            logger.warning("mcp_tool_discovery_failed", server=name, error=str(exc))

    return "\n\n".join(sections)


async def append_mcp_context(
    system_prompt: str,
    mcp_configs: dict[str, MCPServerConfig],
    db: AsyncSession,
) -> str:
    if not mcp_configs:
        return system_prompt

    tools_text = await _discover_tools(mcp_configs)
    if not tools_text.strip():
        return system_prompt

    # Load the mcp-tools skill and inject dynamic tool list
    skill = await skill_service.get_skill(db, "mcp-tools")
    if skill:
        skill_content = skill["content"].replace("{{MCP_TOOLS_LIST}}", tools_text)
        return system_prompt + "\n\n" + skill_content

    # Fallback if skill not in DB
    return (
        system_prompt
        + "\n\nAvailable MCP tools:\n"
        + tools_text
        + '\n\nTo use a tool, respond with ONLY:\n<tool_call>\n{"server": "SERVER_NAME", "tool": "TOOL_NAME", "arguments": {}}\n</tool_call>'
    )
