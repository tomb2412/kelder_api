#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

HOST_API_IMAGE="host-api"
HOST_API_CONTAINER="host_api"
HOST_API_PORT=9090
BUILD="${BUILD:-false}"
ENV_FILE="$PROJECT_ROOT/.env"
PROJECT_MOUNT="$PROJECT_ROOT"
LOG_DIR="$PROJECT_ROOT/logs"

NEO4J_CONTAINER="neo4j"
NEO4J_IMAGE="neo4j:2025.10.1"
DOCKER_NETWORK="kelder_net"

# Allow an optional flag: ./scripts/start_app.sh --build
if [[ "${1:-}" == "--build" || "${1:-}" == "-b" ]]; then
    BUILD="true"
    shift
fi

# ── Docker network ────────────────────────────────────────────────────────────
echo "Ensuring Docker network '$DOCKER_NETWORK' exists..."
docker network create "$DOCKER_NETWORK" 2>/dev/null || true

# ── Neo4j (standalone — data is preserved across restarts) ───────────────────
if docker ps --format '{{.Names}}' | grep -qx "$NEO4J_CONTAINER"; then
    echo "Neo4j is already running."
elif docker ps -a --format '{{.Names}}' | grep -qx "$NEO4J_CONTAINER"; then
    echo "Starting existing Neo4j container (data preserved)..."
    docker start "$NEO4J_CONTAINER"
else
    echo "Creating Neo4j container for the first time..."
    docker run -d \
        --name "$NEO4J_CONTAINER" \
        --network "$DOCKER_NETWORK" \
        -p 7474:7474 \
        -p 7687:7687 \
        -e NEO4J_AUTH=none \
        -e "NEO4J_dbms_security_procedures_allowlist=gds.*, spatial.*" \
        -e "NEO4J_dbms_security_procedures_unrestricted=gds.*, spatial.*" \
        -v "$HOME/neo4j/data:/data" \
        -v "$HOME/neo4j/plugins:/plugins" \
        -v "$HOME/neo4j/imports:/import" \
        "$NEO4J_IMAGE"
    echo "Neo4j container created."
fi

# Ensure Neo4j is connected to the shared network (handles containers created
# before the network existed or by older versions of this script).
if ! docker network inspect "$DOCKER_NETWORK" \
        --format '{{range .Containers}}{{.Name}} {{end}}' \
        2>/dev/null | grep -qw "$NEO4J_CONTAINER"; then
    echo "Connecting Neo4j to '$DOCKER_NETWORK'..."
    docker network connect "$DOCKER_NETWORK" "$NEO4J_CONTAINER"
fi

# ── Host restart API ─────────────────────────────────────────────────────────
if [[ "$BUILD" == "true" ]]; then
    echo "Building host restart API image..."
    docker build -f Dockerfile.host_api -t "$HOST_API_IMAGE" .
else
    echo "Skipping host restart API build (pass --build to enable)."
fi

mkdir -p "$LOG_DIR"

echo "Starting host restart API container..."
docker rm -f "$HOST_API_CONTAINER" >/dev/null 2>&1 || true
docker run -d \
    --name "$HOST_API_CONTAINER" \
    -p "${HOST_API_PORT}:9090" \
    --env-file "$ENV_FILE" \
    -v "$PROJECT_MOUNT:/app" \
    -v "$LOG_DIR:/logs" \
    -v /var/run/docker.sock:/var/run/docker.sock \
    "$HOST_API_IMAGE"

# ── App services (compose) ────────────────────────────────────────────────────
echo "Starting Docker Compose services..."
if [[ "$BUILD" == "true" ]]; then
    docker compose up --build -d
else
    docker compose up -d
fi

echo "All services running."
