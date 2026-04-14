FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VERSION=1.8.5 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN curl -sSL https://install.python-poetry.org | POETRY_VERSION=2.3.4 python3 -
ENV PATH="$POETRY_HOME/bin:$PATH"

WORKDIR /app
COPY pyproject.toml poetry.lock* README.md ./
COPY src/ ./src/


RUN poetry run pip install torch --index-url https://download.pytorch.org/whl/cpu

RUN poetry install --without dev --no-root \
    && poetry install --without dev


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    # HuggingFace model cache inside a named volume
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

ENTRYPOINT ["anagnosi"]
CMD ["--help"]