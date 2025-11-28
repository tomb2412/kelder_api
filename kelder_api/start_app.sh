#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

HOST_API_IMAGE="host-api"
HOST_API_CONTAINER="host_api"
HOST_API_PORT=9090
BUILD="${BUILD:-false}"
ENV_FILE="$SCRIPT_DIR/.env"
PROJECT_MOUNT="$SCRIPT_DIR"

# Allow an optional flag: ./start_app.sh --build
if [[ "${1:-}" == "--build" || "${1:-}" == "-b" ]]; then
    BUILD="true"
    shift
fi

if [[ "$BUILD" == "true" ]]; then
    echo "Building host restart API image..."
    docker build -f Dockerfile.host_api -t "$HOST_API_IMAGE" .
else
    echo "Skipping host restart API build (set BUILD=true or pass --build to enable)."
fi

mkdir -p "$SCRIPT_DIR/logs"

echo "Starting host restart API container..."
docker rm -f "$HOST_API_CONTAINER" >/dev/null 2>&1 || true
docker run -d \
    --name "$HOST_API_CONTAINER" \
    -p "${HOST_API_PORT}:9090" \
    --env-file "$ENV_FILE" \
    -v "$PROJECT_MOUNT:/app" \
    -v "$SCRIPT_DIR/logs:/logs" \
    -v /var/run/docker.sock:/var/run/docker.sock \
    "$HOST_API_IMAGE"

echo "Starting Docker Compose services..."

if [[ "$BUILD" == "true" ]]; then
    docker compose up --build -d
else
    docker compose up -d
fi

echo "All services running."
