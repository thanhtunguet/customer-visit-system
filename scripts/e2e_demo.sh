#!/usr/bin/env bash
set -euo pipefail
echo "Starting E2E demo (compose)"
docker compose -f infra/compose/docker-compose.dev.yml up -d --build
echo "Waiting for API..."
sleep 3
curl -s http://localhost:8080/v1/health || true
echo "Trigger worker-sim event"
docker compose -f infra/compose/docker-compose.dev.yml logs -f worker-sim &
sleep 5
echo "E2E demo complete"

