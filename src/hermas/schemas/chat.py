"""Chat request / response schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    messages: list[dict] = Field(..., min_length=1)
    conversationId: str = ""
    model: str = ""
    baseUrl: str = ""
    apiKey: str = ""
    systemPrompt: str = ""
    temperature: float = 0.2
    maxTokens: int = 1200
    selectedSkillIds: list[str] = Field(default_factory=list)
    autoSkillRouting: bool = True
    mcpServerIds: list[str] = Field(default_factory=list)
    mcpServerId: str = ""


class ChatResponse(BaseModel):
    conversationId: str
    message: dict
    model: str
    usage: dict
    appliedSkillIds: list[str]
