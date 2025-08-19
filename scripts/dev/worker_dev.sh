#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")"/../.. && pwd)
cd "$ROOT_DIR/apps/worker"

python3 -m venv .venv || true
source .venv/bin/activate
python -m pip install --upgrade pip >/dev/null
pip install -r requirements.txt >/dev/null || true

export API_URL=${API_URL:-http://localhost:8080}
export TENANT_ID=${TENANT_ID:-t-dev}
export SITE_ID=${SITE_ID:-s-1}
export CAMERA_ID=${CAMERA_ID:-c-1}
export WORKER_API_KEY=${WORKER_API_KEY:-dev-api-key}

echo "Starting worker-sim against $API_URL"
exec .venv/bin/python -m app.main

