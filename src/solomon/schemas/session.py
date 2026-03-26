"""Session schemas."""

from __future__ import annotations

from pydantic import BaseModel


class SessionCreateRequest(BaseModel):
    userId: str = ""


class SessionCreateResponse(BaseModel):
    sessionToken: str
    userId: str
    expiresAt: int
