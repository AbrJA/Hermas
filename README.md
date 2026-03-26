# 🧠 Solomon

[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com/)
[![License: GPL-3.0](https://img.shields.io/badge/License-GPL%203.0-red.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-148%20passed-brightgreen.svg)](tests/)

> **Production-ready conversational AI assistant** with streaming responses, skill routing, MCP tool integration, and persistent conversation history.

Solomon is a modern backend and lightweight web UI designed for practical local development and extensible production deployments. It combines real-time chat streaming via Server-Sent Events, optional skill-based prompt augmentation, MCP server tool integration, and async persistence—all with strong test coverage.

---

## ✨ Highlights

- 🚀 **Streaming Chat** – Real-time Server-Sent Events at `/api/chat/stream`
- 💬 **Standard Completions** – Non-streaming responses at `/api/chat`
- 📚 **Conversation History** – Load, list, and search past conversations
- 🎯 **Smart Skills** – Upload markdown skills and auto-route with the LLM
- 🔌 **MCP Integration** – Register tools, discover capabilities, execute in context
- 🔐 **Session Management** – Token-based access with optional app token auth
- ⚡ **Async SQLAlchemy** – Fast async persistence with SQLite by default
- 🌐 **Included Frontend** – Clean, vanilla HTML/CSS/JS web UI
- 🐳 **Docker Ready** – Full Docker Compose support for local and production

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | FastAPI + Uvicorn |
| Database | SQLAlchemy Async + aiosqlite |
| LLM | OpenAI Python SDK |
| Streaming | sse-starlette |
| Config | pydantic-settings |
| Logging | structlog |
| Frontend | Vanilla HTML/CSS/JS |
| Testing | pytest (148+ tests) |

## 📁 Project Layout

```
solomon/
├── 📄 docker-compose.yml
├── 🐳 Dockerfile
├── 📦 pyproject.toml
├── 📖 README.md
├── 📂 data/                      # Application data
├── 📂 deploy/
│   └── nginx.conf               # Production reverse proxy config
├── 🎨 public/                    # Frontend assets
│   ├── app.css
│   ├── app.js
│   └── index.html
├── 🐍 src/solomon/
│   ├── config.py
│   ├── database.py
│   ├── main.py
│   ├── api/                     # API endpoints
│   ├── middleware/              # Request middleware
│   ├── models/                  # ORM models
│   ├── schemas/                 # Request/response schemas
│   └── services/                # Business logic
└── 🧪 tests/                     # Test suite
```

## 📋 Requirements

- **Python 3.12+** – Modern async support
- **uv** – Fast Python package manager
- **OpenAI API Key** – For any OpenAI-compatible provider

## 🚀 Quick Start

### 1️⃣ Install Dependencies

```bash
uv sync
```

### 2️⃣ Configure Your Environment

Create `.env` in the project root:

```env
# Server
SOLOMON_HOST=0.0.0.0
SOLOMON_PORT=8080

# LLM Provider
SOLOMON_LLM_BASE_URL=https://api.openai.com
SOLOMON_DEFAULT_MODEL=gpt-4o-mini
SOLOMON_DEFAULT_API_KEY=your_api_key_here

# Prompting
SOLOMON_SYSTEM_PROMPT=You are Solomon, a helpful assistant. Keep answers accurate, concise, and actionable.

# Features
SOLOMON_SKILLS_DIR=skills
SOLOMON_DATA_DIR=data
SOLOMON_CORS_ORIGIN=*
SOLOMON_REQUEST_TIMEOUT_SECONDS=30

# Security
SOLOMON_REQUIRE_AUTH=false
SOLOMON_APP_API_TOKEN=
SOLOMON_SESSION_TTL_SECONDS=86400
```

### 3️⃣ Run the Application

```bash
uv run src/solomon/main.py
```

Or use the script entrypoint:

```bash
uv run solomon
```

✅ Visit **[http://localhost:8080](http://localhost:8080)** in your browser.

## 🐳 Docker

Deploy with Docker Compose in one command:

```bash
docker compose up --build
```

Includes:
- ✅ Application Dockerfile
- ✅ docker-compose.yml orchestration
- ✅ nginx.conf for reverse proxy setup

## 🎯 How It Works

### 💬 Chat Flow

1. Frontend creates a session → `/api/session`
2. Client sends messages → `/api/chat` or `/api/chat/stream`
3. System prompt is built from base + selected skills
4. If MCP servers attached → discover tools + execute loop
5. Final answer is persisted → conversations history API

### 🎨 Skills System

**Skills** are markdown instruction fragments stored in the database.

- Upload new skills from `.md` files
- Manually select candidate skills per request
- Enable `autoSkillRouting=true` → LLM picks the best match
- If no skill applies → standard assistant behavior

### 🔌 MCP (Model Context Protocol)

Solomon integrates remote MCP servers for runtime tools:

- Register MCP server configs (per user)
- Discover available tools via `/api/mcp/tools`
- Model can emit `<tool_call>` blocks during chat
- Backend executes tools in a controlled loop
- Tool results fed back into context

**Safety controls:**
- Bounded tool iterations
- Tool result truncation
- Structured failure logging

## ⚙️ Configuration

All settings load from `.env` with the `SOLOMON_` prefix.

### 🔧 Core Settings

| Variable | Purpose | Default |
|----------|---------|---------|
| `SOLOMON_HOST` | Server bind host | `0.0.0.0` |
| `SOLOMON_PORT` | Server bind port | `8080` |
| `SOLOMON_LLM_BASE_URL` | LLM provider URL | `https://api.openai.com` |
| `SOLOMON_DEFAULT_MODEL` | Default model/deployment | `gpt-4o-mini` |
| `SOLOMON_DEFAULT_API_KEY` | Backend API key | *(required)* |
| `SOLOMON_SYSTEM_PROMPT` | Base assistant prompt | *(see example)* |
| `SOLOMON_REQUEST_TIMEOUT_SECONDS` | Request timeout | `30` |

### 🔐 Auth Settings

| Variable | Purpose | Default |
|----------|---------|---------|
| `SOLOMON_REQUIRE_AUTH` | Enforce auth checks | `false` |
| `SOLOMON_APP_API_TOKEN` | App-level access token | *(optional)* |
| `SOLOMON_SESSION_TTL_SECONDS` | Session lifetime | `86400` |

## 🔌 API Endpoints

### Health & Config

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/api/health` | Service health check |
| `GET` | `/api/readiness` | Readiness probe |
| `GET` | `/api/config` | Client-facing config |

### 💬 Chat

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/chat` | Standard completion |
| `POST` | `/api/chat/stream` | SSE streaming completion |

### 📚 Conversations

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/api/conversations/list` | List all conversations |
| `GET` | `/api/conversations/load?id=...` | Load specific conversation |
| `GET` | `/api/conversations/search?q=...` | Search conversations |

### 🎨 Skills

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/api/skills` | List all skills |
| `GET` | `/api/skills/{skill_id}` | Get skill details |
| `POST` | `/api/skills` | Create skill |
| `POST` | `/api/skills/upload` | Upload `.md` skill file |
| `DELETE` | `/api/skills/{skill_id}` | Delete skill |

### 🔌 MCP

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/api/mcp/servers` | List user MCP servers |
| `POST` | `/api/mcp/servers` | Register MCP server |
| `DELETE` | `/api/mcp/servers/{id}` | Unregister server |
| `POST` | `/api/mcp/tools` | Discover server tools |
| `POST` | `/api/mcp/call` | Execute tool

## 📡 Streaming Response Model

The `/api/chat/stream` endpoint emits **Server-Sent Events (SSE)** with JSON payloads.

Event types:
| Event | Payload | Purpose |
|-------|---------|---------|
| `start` | `{conversationId, model, appliedSkillIds}` | Initialization |
| `tool_start` | `{iteration, server, tool}` | Tool call begins |
| `tool_done` | `{iteration, server, tool, resultLength}` | Tool call ends |
| `token` | `{delta}` | Incremental output chunk |
| `done` | `{conversationId, content, appliedSkillIds}` | Final message |

This design allows frontends to render progressive output while ensuring the final canonical message is preserved for storage.

## 💻 Example Usage

### ✅ Create a Session

```bash
curl -X POST http://localhost:8080/api/session \
  -H "Content-Type: application/json" \
  -d '{"userId":"user123"}'
```

### 💬 Send a Chat Request

```bash
curl -X POST http://localhost:8080/api/chat \
  -H "Content-Type: application/json" \
  -H "X-Session-Token: <token>" \
  -H "X-User-Id: user123" \
  -d '{
    "messages": [{"role": "user", "content": "Hello"}],
    "model": "gpt-4o-mini",
    "selectedSkillIds": [],
    "autoSkillRouting": true
  }'
```

### 🚀 Stream a Response

```bash
curl -N -X POST http://localhost:8080/api/chat/stream \
  -H "Content-Type: application/json" \
  -H "X-Session-Token: <token>" \
  -H "X-User-Id: user123" \
  -d '{
    "messages": [{"role": "user", "content": "Explain SSE"}],
    "model": "gpt-4o-mini",
    "selectedSkillIds": [],
    "autoSkillRouting": true
  }'
```

## 🧪 Development

### Run All Tests

```bash
uv run pytest tests/ -v
```

**Coverage:** 148+ tests across services, API, streaming, prompt building, MCP, and middleware.

### Run Linting

```bash
uv run ruff check src tests
```

### Architecture Notes

- **API Layer** (`src/solomon/api/`) – Route handlers, dependency injection
- **Services** (`src/solomon/services/`) – Business logic, orchestration
- **Models** (`src/solomon/models/`) – SQLAlchemy ORM
- **Schemas** (`src/solomon/schemas/`) – Request/response contracts
- **Frontend** (`public/`) – Vanilla HTML/CSS/JS UI

## 🔧 Troubleshooting

### ❌ `LLM endpoint/model not found (404)`

**Error:** Provider returns 404 when calling the model.

**Check:**
- ✅ `SOLOMON_LLM_BASE_URL` is correct
- ✅ `SOLOMON_DEFAULT_MODEL` exists and is enabled
- ✅ API key belongs to the right project/account

**For OpenAI:**
```env
SOLOMON_LLM_BASE_URL=https://api.openai.com
SOLOMON_DEFAULT_MODEL=gpt-4o-mini
```

### ❌ Empty Streamed Responses

**Problem:** UI shows `(Empty response)` even though the model responds.

**Solution:** Verify SSE events are encoding correctly and reaching the browser. Latest code paths ensure proper encoding.

### ❌ MCP Tools Not Appearing

**Check:**
- ✅ MCP server URL is reachable
- ✅ Auth headers are correct (if required)
- ✅ `/api/mcp/tools` endpoint returns tools

### ❌ Auth Failures

**If** `SOLOMON_REQUIRE_AUTH=true`:

Required headers on every request:
- `X-App-Token` (session creation, if configured)
- `X-Session-Token`
- `X-User-Id`

## 📊 Testing

Comprehensive test suite with **148+ passing tests** across:

- ✅ Configuration loading
- ✅ Chat services (streaming & standard)
- ✅ Prompt building and skill routing
- ✅ MCP integration
- ✅ Middleware and error handling
- ✅ API endpoints

**Run full suite:**

```bash
uv run pytest tests/ -v
```

---

## 📄 License

Solomon is licensed under the **GNU General Public License v3.0 (GPL-3.0)**.

### Summary

This software is free and open-source under the GPL-3.0 license:

- **Freedom to use** – For any purpose
- **Freedom to modify** – Access to source code
- **Freedom to distribute** – Under the same GPL-3.0 terms
- **Must include license** – When distributing
- **Must provide source** – Derivative works also under GPL-3.0

### Full License Text

```
Solomon - Conversational AI Assistant
Copyright (c) 2026 AbrJA

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
```

---

## 🙏 Acknowledgments

Built with ❤️ using:
- [FastAPI](https://fastapi.tiangolo.com/)
- [SQLAlchemy](https://www.sqlalchemy.org/)
- [OpenAI Python SDK](https://github.com/openai/openai-python)
- [sse-starlette](https://github.com/sysid/sse-starlette)
- [pydantic](https://docs.pydantic.dev/)

---

**Made with ☕ by the Solomon team**
