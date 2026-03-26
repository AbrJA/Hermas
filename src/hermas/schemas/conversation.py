"""Conversation schemas."""

from __future__ import annotations

from pydantic import BaseModel


class ConversationSummary(BaseModel):
    id: str
    title: str
    updatedAt: str
    model: str


class ConversationDetail(BaseModel):
    id: str
    title: str
    model: str
    createdAt: str
    updatedAt: str
    messages: list[dict]
