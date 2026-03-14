#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

HOST_API_CONTAINER="host_api"
NEO4J_CONTAINER="neo4j"

[[ "${1:-}" == "--prune" || "${1:-}" == "-p" ]] && PRUNE=true || PRUNE=false

# ── Host API ──────────────────────────────────────────────────────────────────
echo "Stopping host API..."
docker rm -f "$HOST_API_CONTAINER" 2>/dev/null || true

# ── Compose services ──────────────────────────────────────────────────────────
echo "Stopping compose services..."
docker compose -p kelder down

# ── Neo4j ─────────────────────────────────────────────────────────────────────
echo "Stopping Neo4j (data preserved)..."
docker stop "$NEO4J_CONTAINER" 2>/dev/null || true

# ── Prune ─────────────────────────────────────────────────────────────────────
if $PRUNE; then
    echo "Pruning Docker resources..."
    docker container prune -f
    docker image prune -f
    docker builder prune -f
fi

echo "✅ All services stopped."