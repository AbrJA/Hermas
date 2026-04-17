"""Chat endpoints – synchronous and SSE streaming."""

from __future__ import annotations

from io import BytesIO
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from hermas.api.dependencies import get_app_config, get_db, require_session
from hermas.config import AppConfig
from hermas.services import chat_service

router = APIRouter(prefix="/api", tags=["chat"])

_MAX_ATTACHMENT_CHARS = 50000


@router.post("/chat")
async def chat(
    request: Request,
    cfg: Annotated[AppConfig, Depends(get_app_config)],
    user_id: Annotated[str, Depends(require_session)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    payload = await request.json()
    result = await chat_service.complete_chat(cfg, user_id, payload, db)
    return JSONResponse({
        "conversationId": result["conversationId"],
        "message": {"role": "assistant", "content": result["content"]},
        "model": result["model"],
        "usage": result["usage"],
        "appliedSkillIds": result["appliedSkillIds"],
    })


@router.post("/chat/stream")
async def chat_stream(
    request: Request,
    cfg: Annotated[AppConfig, Depends(get_app_config)],
    user_id: Annotated[str, Depends(require_session)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    payload = await request.json()

    async def event_generator():
        async for event_str in chat_service.complete_chat_stream(cfg, user_id, payload, db):
            yield event_str.encode("utf-8")

    return EventSourceResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-cache",
        },
    )


@router.post("/chat/attachments/extract")
async def extract_chat_attachment(
    file: UploadFile = File(...),
    user_id: Annotated[str, Depends(require_session)] = "",
):
    del user_id

    filename = (file.filename or "").strip()
    if not filename:
        raise HTTPException(400, detail="Attachment filename is required")

    if not filename.lower().endswith(".pdf"):
        raise HTTPException(400, detail="Only .pdf files are accepted for chat attachments")

    raw = await file.read()
    if not raw:
        raise HTTPException(400, detail="Uploaded PDF is empty")

    try:
        from pypdf import PdfReader
    except Exception as exc:  # pragma: no cover - dependency should exist in runtime env
        raise HTTPException(500, detail="PDF support is not available on this server") from exc

    try:
        reader = PdfReader(BytesIO(raw))
        extracted_chunks: list[str] = []
        for page in reader.pages:
            text = page.extract_text() or ""
            if text.strip():
                extracted_chunks.append(text.strip())
        extracted_text = "\n\n".join(extracted_chunks)
    except Exception as exc:
        raise HTTPException(400, detail=f"Could not parse PDF: {exc}") from exc

    if not extracted_text.strip():
        raise HTTPException(400, detail="No readable text was found in the PDF")

    truncated = len(extracted_text) > _MAX_ATTACHMENT_CHARS
    text_for_chat = extracted_text[:_MAX_ATTACHMENT_CHARS]

    return {
        "filename": filename,
        "pages": len(reader.pages),
        "text": text_for_chat,
        "truncated": truncated,
        "maxChars": _MAX_ATTACHMENT_CHARS,
    }
