FROM python:3.12-slim-bookworm AS base

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    python3-gpiozero \
    python3-rpi.gpio \
    && rm -rf /var/lib/apt/lists/*

# Copy uv from official image (pinned version)
COPY --from=ghcr.io/astral-sh/uv:0.8.17 /uv /uvx /bin/

WORKDIR /app

# Copy dependency files first (for build cache)
COPY pyproject.toml uv.lock* README.md ./
RUN uv sync --locked --no-install-project

# Copy the rest of the source
COPY src/ src/

# Install deps into venv (requires lockfile to be fresh)
RUN uv sync --locked

ENV PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random

EXPOSE 80

CMD ["uv", "run", "uvicorn", "src.kelder_api.app.main:app", "--host", "0.0.0.0", "--port", "80", "--proxy-headers"]
