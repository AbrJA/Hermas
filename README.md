# Solomon

Production-ready conversational AI assistant built with FastAPI, streaming chat responses, skill routing, MCP tool integration, and persistent conversation history.

Solomon combines a lightweight web UI with a backend designed for practical local development and extensible production deployments. It supports direct chat completions, SSE streaming, optional skill-based prompt augmentation, MCP server registration and tool execution, and async persistence for sessions and conversations.

## Highlights

- Streaming chat via Server-Sent Events at `/api/chat/stream`
- Standard non-streaming chat completions at `/api/chat`
- Conversation history, loading, and search
- Session-based access flow with optional app token enforcement
- Markdown skill upload and storage
- Optional LLM-based auto skill routing
- MCP server management, tool discovery, and tool execution loop
- OpenAI and OpenAI-compatible backend support
- Async SQLAlchemy persistence with SQLite by default
- Frontend included in `public/`
- Docker and `uv` workflows

## Tech Stack

- Python 3.12+
- FastAPI
- Uvicorn
- SQLAlchemy Async + aiosqlite
- OpenAI Python SDK
- sse-starlette
- pydantic-settings
- structlog
- Vanilla HTML, CSS, and JavaScript frontend
- pytest for test coverage

## Project Layout

```text
docker-compose.yml
Dockerfile
pyproject.toml
README.md
data/
deploy/
	nginx.conf
public/
	app.css
	app.js
	index.html
src/
	solomon/
		config.py
		database.py
		main.py
		api/
		middleware/
		models/
		schemas/
		services/
tests/
```

## Requirements

- Python 3.12 or newer
- `uv` installed
- An API key for OpenAI or another OpenAI-compatible provider

## Quick Start

### 1. Install dependencies

```bash
uv sync
```

### 2. Create your environment file

Create `.env` in the project root:

```env
SOLOMON_HOST=0.0.0.0
SOLOMON_PORT=8080

SOLOMON_LLM_BASE_URL=https://api.openai.com
SOLOMON_DEFAULT_MODEL=gpt-4o-mini
SOLOMON_DEFAULT_API_KEY=your_api_key_here

SOLOMON_SYSTEM_PROMPT=You are Solomon, a helpful assistant. Keep answers accurate, concise, and actionable.
SOLOMON_SKILLS_DIR=skills
SOLOMON_DATA_DIR=data
SOLOMON_CORS_ORIGIN=*
SOLOMON_REQUEST_TIMEOUT_SECONDS=30

SOLOMON_REQUIRE_AUTH=false
SOLOMON_APP_API_TOKEN=
SOLOMON_SESSION_TTL_SECONDS=86400
```

### 3. Start the app

Either run the module entrypoint:

```bash
uv run src/solomon/main.py
```

Or use the installed script entrypoint:

```bash
uv run solomon
```

The application starts on `http://localhost:8080` by default.

## Docker

Build and run with Docker Compose:

```bash
docker compose up --build
```

This project includes:

- `Dockerfile` for the application image
- `docker-compose.yml` for local orchestration
- `deploy/nginx.conf` for reverse proxy deployment support

## How It Works

### Chat Flow

1. The frontend creates a session with `/api/session`.
2. The client sends chat payloads to `/api/chat` or `/api/chat/stream`.
3. Solomon builds a system prompt from the base prompt plus any selected or auto-routed skills.
4. If MCP servers are attached, Solomon discovers tools and can run a tool loop before producing the final answer.
5. Conversations are persisted and can be listed, loaded, or searched later.

### Skills

Skills are markdown-defined prompt fragments stored in the database.

- Skills can be uploaded from `.md` files
- Users can manually select candidate skills
- With `autoSkillRouting=true`, the LLM chooses the best matching skill from the selected candidates
- If no skill clearly applies, Solomon answers normally without injecting optional skill context

### MCP Tooling

Solomon supports Model Context Protocol servers as runtime tools.

- Register per-user MCP servers
- Discover available tools from a server
- Let the model emit tool calls in a controlled loop
- Feed tool results back into the model before the final answer

The chat service enforces:

- bounded tool iterations
- tool result truncation
- structured failure logging

## Configuration

Configuration is loaded from `.env` with the `SOLOMON_` prefix.

### Core Settings

- `SOLOMON_HOST`: bind host, default `0.0.0.0`
- `SOLOMON_PORT`: bind port, default `8080`
- `SOLOMON_LLM_BASE_URL`: provider base URL, for OpenAI use `https://api.openai.com`
- `SOLOMON_DEFAULT_MODEL`: default chat model or Azure deployment name
- `SOLOMON_DEFAULT_API_KEY`: backend API key if the frontend does not provide one
- `SOLOMON_SYSTEM_PROMPT`: base assistant system prompt
- `SOLOMON_REQUEST_TIMEOUT_SECONDS`: timeout for LLM and tool calls
- `SOLOMON_SKILLS_DIR`: filesystem directory seeded for skills on boot
- `SOLOMON_DATA_DIR`: application data directory

### Auth Settings

- `SOLOMON_REQUIRE_AUTH`: enables app/session auth checks
- `SOLOMON_APP_API_TOKEN`: optional app token required for session creation
- `SOLOMON_SESSION_TTL_SECONDS`: session lifetime in seconds

## API Overview

### Health and Config

- `GET /api/health`
- `GET /api/readiness`
- `GET /api/config`

### Sessions

- `POST /api/session`

### Chat

- `POST /api/chat`
- `POST /api/chat/stream`

### Conversations

- `GET /api/conversations/list`
- `GET /api/conversations/load?id=<conversation_id>`
- `GET /api/conversations/search?q=<text>`

### Skills

- `GET /api/skills`
- `GET /api/skills/{skill_id}`
- `POST /api/skills`
- `POST /api/skills/upload`
- `DELETE /api/skills/{skill_id}`

### MCP

- `GET /api/mcp/servers`
- `POST /api/mcp/servers`
- `DELETE /api/mcp/servers/{server_id}`
- `POST /api/mcp/tools`
- `POST /api/mcp/call`

## Streaming Response Model

The streaming endpoint emits SSE events with JSON payloads. Event types include:

- `start`: initial metadata such as `conversationId`, model, and applied skill IDs
- `tool_start`: emitted when a tool call begins
- `tool_done`: emitted when a tool call completes
- `token`: incremental text output in `delta`
- `done`: final content envelope

This makes it easy for the frontend to display progressive output while preserving the final canonical assistant message for persistence.

## Example Usage

### Create a session

```bash
curl -X POST http://localhost:8080/api/session \
	-H "Content-Type: application/json" \
	-d '{"userId":"anonymous"}'
```

### Send a normal chat request

```bash
curl -X POST http://localhost:8080/api/chat \
	-H "Content-Type: application/json" \
	-H "X-Session-Token: <session_token>" \
	-H "X-User-Id: anonymous" \
	-d '{
		"messages": [{"role": "user", "content": "Hello"}],
		"model": "gpt-4o-mini",
		"baseUrl": "https://api.openai.com",
		"selectedSkillIds": [],
		"autoSkillRouting": true,
		"mcpServers": []
	}'
```

### Send a streaming chat request

```bash
curl -N -X POST http://localhost:8080/api/chat/stream \
	-H "Content-Type: application/json" \
	-H "X-Session-Token: <session_token>" \
	-H "X-User-Id: anonymous" \
	-d '{
		"messages": [{"role": "user", "content": "Summarize this project"}],
		"model": "gpt-4o-mini",
		"baseUrl": "https://api.openai.com",
		"selectedSkillIds": [],
		"autoSkillRouting": true,
		"mcpServers": []
	}'
```

## Development

### Run tests

```bash
uv run pytest tests/ -q
```

### Run linting

```bash
uv run ruff check src tests
```

### Design Notes

- API route translation lives in `src/solomon/api/`
- Core orchestration logic lives in `src/solomon/services/`
- Persistence models live in `src/solomon/models/`
- Request and response contracts live in `src/solomon/schemas/`
- Static frontend assets live in `public/`

## Troubleshooting

### 404 from the LLM provider

If you see warnings such as `LLM endpoint/model not found (404)`, verify:

- `SOLOMON_LLM_BASE_URL` is correct for your provider
- `SOLOMON_DEFAULT_MODEL` exists and is enabled for your API key
- your API key belongs to the expected project/account

For standard OpenAI usage:

```env
SOLOMON_LLM_BASE_URL=https://api.openai.com
SOLOMON_DEFAULT_MODEL=gpt-4o-mini
```

### Empty streamed responses

If the UI shows an empty response, check that SSE events are reaching the browser correctly and that the app is running the latest code path for encoded SSE output.

### MCP tools not appearing

Check:

- the saved MCP server URL
- auth header name and value
- `/api/mcp/tools` response for that server

### Session or auth problems

If auth is enabled, make sure requests send the required headers:

- `X-App-Token` when creating a session, if configured
- `X-Session-Token`
- `X-User-Id`

## Testing Status

The repository includes an extensive automated test suite covering configuration, chat services, streaming, prompt building, MCP integration, middleware, and API behavior.

Run everything with:

```bash
uv run pytest tests/ -q
```

## License

No license is declared yet. Add the appropriate license for your intended distribution model.
