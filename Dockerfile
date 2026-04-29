FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        build-essential \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/

RUN uv sync --no-dev --frozen

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    HF_HOME="/cache/huggingface" \
    TRANSFORMERS_CACHE="/cache/huggingface"

RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /app/.venv  ./.venv
COPY --from=builder /app/src    ./src

RUN mkdir -p /data /cache/huggingface

VOLUME ["/data", "/cache"]

ENV APP_ROOT_PATH=/data \
    OLLAMA_BASE_URL=http://ollama:11434 \
    DEBUG_MODE=false

ENTRYPOINT []
CMD ["python", "-m", "anagnosi.connections.telegram_bot"]
