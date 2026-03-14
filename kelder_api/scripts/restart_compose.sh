#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

COMPOSE_PROJECT="kelder"

echo "Flushing Redis..."
docker exec redis redis-cli FLUSHALL || true

echo "Stopping compose services..."
docker compose -p "$COMPOSE_PROJECT" down

echo "Restarting services..."
docker compose -p "$COMPOSE_PROJECT" up -d --no-build

echo "✅ Done."