FROM python:3.12-slim-bookworm AS base

# System deps
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    gnupg && \
    install -m 0755 -d /etc/apt/keyrings && \
    curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg && \
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
      https://download.docker.com/linux/debian \
      $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
      > /etc/apt/sources.list.d/docker.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    python3-gpiozero \
    python3-rpi.gpio \
    docker-ce-cli \
    docker-compose-plugin && \
    rm -rf /var/lib/apt/lists/*

# Copy uv from official image (pinned version)
COPY --from=ghcr.io/astral-sh/uv:0.8.17 /uv /uvx /bin/

WORKDIR /app

# Copy dependency files first (for build cache)
COPY pyproject.toml uv.lock* README.md docker-compose.yml Dockerfile ./
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
