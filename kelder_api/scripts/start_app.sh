#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

DOCKER_NETWORK="kelder_net"
NEO4J_CONTAINER="neo4j"
NEO4J_IMAGE="neo4j:2025.10.1"
HOST_API_CONTAINER="host_api"
HOST_API_IMAGE="host-api"
HOST_API_PORT=9090
BUILD=false

[[ "${1:-}" == "--build" || "${1:-}" == "-b" ]] && BUILD=true

# ── Network ───────────────────────────────────────────────────────────────────
echo "Ensuring network '$DOCKER_NETWORK' exists..."
docker network create "$DOCKER_NETWORK" 2>/dev/null || true

# ── Neo4j ─────────────────────────────────────────────────────────────────────
if docker ps --format '{{.Names}}' | grep -qx "$NEO4J_CONTAINER"; then
    echo "Neo4j already running."
elif docker ps -a --format '{{.Names}}' | grep -qx "$NEO4J_CONTAINER"; then
    echo "Starting existing Neo4j container (data preserved)..."
    docker start "$NEO4J_CONTAINER"
else
    echo "Creating Neo4j container for the first time..."
    docker run -d \
        --name "$NEO4J_CONTAINER" \
        --network "$DOCKER_NETWORK" \
        -p 7474:7474 -p 7687:7687 \
        -e NEO4J_AUTH=none \
        -e "NEO4J_dbms_security_procedures_allowlist=gds.*, spatial.*" \
        -e "NEO4J_dbms_security_procedures_unrestricted=gds.*, spatial.*" \
        -v "$HOME/neo4j/data:/data" \
        -v "$HOME/neo4j/plugins:/plugins" \
        -v "$HOME/neo4j/imports:/import" \
        "$NEO4J_IMAGE"
fi

# Ensure Neo4j is on the shared network
docker network inspect "$DOCKER_NETWORK" --format '{{range .Containers}}{{.Name}} {{end}}' \
    | grep -qw "$NEO4J_CONTAINER" || docker network connect "$DOCKER_NETWORK" "$NEO4J_CONTAINER"

# ── Host API ──────────────────────────────────────────────────────────────────
if $BUILD; then
    echo "Building host API image..."
    docker build -f Dockerfile.host_api -t "$HOST_API_IMAGE" .
fi

mkdir -p "$PROJECT_ROOT/logs" "$PROJECT_ROOT/journey_history"

echo "Starting host API..."
docker rm -f "$HOST_API_CONTAINER" 2>/dev/null || true
docker run -d \
    --name "$HOST_API_CONTAINER" \
    -p "${HOST_API_PORT}:9090" \
    --env-file "$PROJECT_ROOT/.env" \
    -e HOST_PROJECT_ROOT="$PROJECT_ROOT" \
    -v "$PROJECT_ROOT:/app" \
    -v "$PROJECT_ROOT/logs:/logs" \
    -v /var/run/docker.sock:/var/run/docker.sock \
    "$HOST_API_IMAGE"

# ── Compose services ──────────────────────────────────────────────────────────
echo "Starting compose services..."
$BUILD && docker compose -p kelder build
docker compose -p kelder up -d --no-build

echo "✅ All services running."