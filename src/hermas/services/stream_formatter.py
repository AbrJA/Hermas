"""SSE stream formatting helpers."""

from __future__ import annotations

import json


def sse_event(name: str, data: dict) -> str:
    return f"event: {name}\ndata: {json.dumps(data)}\n\n"
