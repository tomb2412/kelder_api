#!/usr/bin/env bash
set -euo pipefail

# Move to the directory containing this script
cd "$(dirname "$0")"

# Uvicorn module path (this must match your Python package layout)
MODULE_PATH="kelder_api.app.host_api:app"

PORT=9090

echo "Starting host restart API..."
uvicorn $MODULE_PATH \
    --host 0.0.0.0 \
    --port $PORT \
    &
API_PID=$!

echo $API_PID > uvicorn.pid
echo "API started with PID $API_PID"
echo "Starting Docker Compose services..."

docker compose up --build -d

echo "All services running."

