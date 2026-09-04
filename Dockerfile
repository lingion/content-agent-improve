# Content Agent API — Playwright-capable backend
# Base image ships Playwright Python + all Chromium system deps.
FROM mcr.microsoft.com/playwright/python:v1.49.0-noble

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # Cap native thread pools (chromadb grpc, numpy) so background threads
    # cannot multiply under memory pressure.
    OMP_NUM_THREADS=2 \
    OPENBLAS_NUM_THREADS=2 \
    API_BASE_URL=http://127.0.0.1:8918

WORKDIR /app

# Install uv (fast resolver, matches uv.lock) and Python deps first so the
# dependency layer caches independently of source edits.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# socat: in-container TCP forwarder for the LiteLLM gateway whose TLS cert
# only covers localhost/127.0.0.1 (see api/server.py _start_gateway_forwarder).
RUN apt-get update && apt-get install -y --no-install-recommends socat \
    && rm -rf /var/lib/apt/lists/*

# Playwright browsers: base image has no browser binaries downloaded yet.
RUN uv run playwright install chromium

COPY agent/ agent/
COPY api/ api/

# Data persisted via volume mounts: ./data (SQLite + vector store + images)
# and ./articles (team article library with git history).
RUN mkdir -p data/images articles

EXPOSE 8918

# Production server (no --reload). One worker: LangGraph state is in-process
# and the paraphrase run lock is a threading lock.
CMD ["uv", "run", "uvicorn", "api.server:app", "--host", "0.0.0.0", "--port", "8918", "--workers", "1"]
