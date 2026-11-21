# Repository import worker for a persistent host (Render background worker).
# It polls the same Aura queue as the scheduled GitHub Actions worker; database leases keep them from colliding.
# Imported repositories are cloned and read as data. Their scripts, hooks and dependencies never run.
FROM ghcr.io/astral-sh/uv:0.12.13-python3.12-trixie-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 worker

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UNTANGLE_CACHE_DIR=/app/.cache \
    LLM_BACKEND=fake \
    EMBED_BACKEND=fastembed \
    EMBED_MODEL=BAAI/bge-small-en-v1.5 \
    EMBED_DIM=384 \
    GIT_TERMINAL_PROMPT=0 \
    PYTHONUNBUFFERED=1

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project
COPY src ./src
COPY cypher ./cypher
RUN uv sync --locked --no-dev \
    && uv run --no-sync python -c "from untangle.embed import FastEmbedder; FastEmbedder('BAAI/bge-small-en-v1.5', 384).embed(['warm'])" \
    && chown -R worker:worker /app

USER worker
ENV PATH="/app/.venv/bin:$PATH"
CMD ["untangle", "import-worker", "--poll", "15"]
