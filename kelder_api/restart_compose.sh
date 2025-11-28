#!/usr/bin/env bash
set -euo pipefail

# Always operate from the script directory
cd "$(dirname "$0")"

echo "Restarting Docker Compose services..."
docker compose down || true
docker compose up --build -d || true

echo ""
echo "Checking container states..."
SERVICES=$(docker compose config --services)

FAILED=0

for SERVICE in $SERVICES; do
    CONTAINER_ID=$(docker compose ps -q "$SERVICE" || true)

    if [ -z "$CONTAINER_ID" ]; then
        echo "✖ $SERVICE → container missing, recreating..."
        docker compose up -d "$SERVICE" || true

        # Re-check after recreate
        CONTAINER_ID=$(docker compose ps -q "$SERVICE" || true)
        if [ -z "$CONTAINER_ID" ]; then
            echo "❌ $SERVICE still has no container after recreate."
            FAILED=1
        else
            echo "✔ $SERVICE container created."
        fi

        continue
    fi

    STATUS=$(docker inspect -f '{{.State.Status}}' "$CONTAINER_ID" 2>/dev/null || echo "unknown")

    if [ "$STATUS" = "running" ]; then
        echo "✔ $SERVICE is running"
    else
        echo "✖ $SERVICE → status: $STATUS"
        FAILED=1
    fi
done

echo ""

if [ $FAILED -eq 0 ]; then
    echo "✅ All services restarted or recreated successfully."
    exit 0
else
    echo "❌ One or more services failed to restart or recreate."
    exit 1
fi
