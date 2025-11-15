#!/usr/bin/env bash
set -euo pipefail

PORT=9090

echo "Stopping host restart API (port $PORT)..."

# Get ALL PIDs listening on the port (each on its own line)
PIDS=$(lsof -ti :$PORT 2>/dev/null || true)

if [ -z "$PIDS" ]; then
    echo "No API process running on port $PORT."
else
    echo "Found running PIDs:"
    echo "$PIDS"

    # Kill each PID one by one
    while IFS= read -r PID; do
        if [[ "$PID" =~ ^[0-9]+$ ]]; then
            echo "Killing PID: $PID"
            kill "$PID" || true
        fi
    done <<< "$PIDS"

    # Wait briefly
    sleep 1

    # Force kill if anything is left
    LEFT=$(lsof -ti :$PORT 2>/dev/null || true)
    if [ -n "$LEFT" ]; then
        echo "Force killing remaining PIDs:"
        echo "$LEFT"
        while IFS= read -r PID; do
            kill -9 "$PID" || true
        done <<< "$LEFT"
    fi
fi

echo "Stopping Docker containers..."
docker compose down || true

echo "Cleaning Docker resources..."

docker container prune -f
docker image prune -f
docker builder prune -f

echo "Docker cleanup complete."


echo "All services stopped."
