#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

HOST_API_CONTAINER="host_api"
NEO4J_CONTAINER="neo4j"
PORT=9090
PRUNE="${PRUNE:-false}"

# Allow an optional flag: ./scripts/stop_app.sh --prune
if [[ "${1:-}" == "--prune" || "${1:-}" == "-p" ]]; then
    PRUNE="true"
    shift
fi

# ── Host restart API ─────────────────────────────────────────────────────────
echo "Stopping host restart API container..."
if docker ps -a --format '{{.Names}}' | grep -qx "$HOST_API_CONTAINER"; then
    docker stop "$HOST_API_CONTAINER" >/dev/null || true
    docker rm   "$HOST_API_CONTAINER" >/dev/null || true
    echo "Host restart API container stopped."
else
    echo "No host restart API container found."
fi

# Fallback: clean up any stray local process still bound to the port
echo "Checking for stray processes on port $PORT..."
PIDS=$(lsof -ti :$PORT 2>/dev/null || true)
if [ -n "$PIDS" ]; then
    while IFS= read -r PID; do
        if [[ "$PID" =~ ^[0-9]+$ ]]; then
            kill "$PID" || true
        fi
    done <<< "$PIDS"
fi

# ── App services (compose) — Neo4j is NOT managed here ───────────────────────
echo "Stopping Docker Compose services (Neo4j is unaffected)..."
docker compose down || true

# ── Neo4j — stop container but preserve data volumes ─────────────────────────
echo "Stopping Neo4j container (data preserved)..."
if docker ps --format '{{.Names}}' | grep -qx "$NEO4J_CONTAINER"; then
    docker stop "$NEO4J_CONTAINER" >/dev/null
    echo "Neo4j stopped."
else
    echo "Neo4j is not running."
fi

if [[ "$PRUNE" == "true" ]]; then
    echo "Pruning Docker resources (Neo4j volumes are excluded)..."
    docker container prune -f
    docker image prune -f
    docker builder prune -f
    echo "Docker cleanup complete."
else
    echo "Skipping Docker resource prune (pass --prune to enable)."
fi

echo "All services stopped."
