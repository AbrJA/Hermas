"""Shared types: LLM usage and result schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class LLMUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    reasoning_tokens: int = 0
    cost: float = 0.0
    elapsed: float = 0.0
    model_id: str = ""

    def to_camel_dict(self) -> dict:
        return {
            "inputTokens": self.input_tokens,
            "outputTokens": self.output_tokens,
            "cacheReadTokens": self.cache_read_tokens,
            "cacheWriteTokens": self.cache_write_tokens,
            "reasoningTokens": self.reasoning_tokens,
            "cost": self.cost,
            "elapsed": self.elapsed,
            "modelId": self.model_id,
        }


class LLMResult(BaseModel):
    content: str = ""
    model: str = ""
    usage: LLMUsage = Field(default_factory=LLMUsage)

    def to_camel_dict(self) -> dict:
        return {
            "content": self.content,
            "model": self.model,
            "usage": self.usage.to_camel_dict(),
        }
