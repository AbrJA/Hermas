"""Tests for chat API endpoints."""

from __future__ import annotations

import sys
import types

import pytest


@pytest.mark.asyncio
async def test_extract_chat_attachment_rejects_non_pdf(client):
    response = await client.post(
        "/api/chat/attachments/extract",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 400
    assert "Only .pdf files" in response.json().get("detail", "")


@pytest.mark.asyncio
async def test_extract_chat_attachment_pdf_success_with_text(client, monkeypatch):
    class _FakePage:
        def extract_text(self):
            return "Project summary from PDF"

    class _FakePdfReader:
        def __init__(self, _stream):
            self.pages = [_FakePage(), _FakePage()]

    fake_module = types.SimpleNamespace(PdfReader=_FakePdfReader)
    monkeypatch.setitem(sys.modules, "pypdf", fake_module)

    response = await client.post(
        "/api/chat/attachments/extract",
        files={"file": ("report.pdf", b"%PDF-1.4\n", "application/pdf")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "report.pdf"
    assert data["pages"] == 2
    assert "Project summary from PDF" in data["text"]
    assert data["truncated"] is False
