"""Skill schemas."""

from __future__ import annotations

from pydantic import BaseModel


class SkillSummary(BaseModel):
    id: str
    name: str
    description: str
    updatedAt: str


class SkillDetail(BaseModel):
    id: str
    name: str
    description: str
    systemPrompt: str


class SkillCreateRequest(BaseModel):
    id: str = ""
    name: str
    description: str = "No description provided"
    content: str
