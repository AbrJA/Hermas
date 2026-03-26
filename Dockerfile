FROM python:3.12-slim AS base

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files first (layer caching)
COPY pyproject.toml uv.lock* ./

# Install dependencies
RUN uv sync --frozen --no-dev

# Copy application code
COPY src ./src
COPY public ./public

# Copy .env.example as fallback
COPY .env.example ./

EXPOSE 8080

CMD ["uv", "run", "solomon"]
