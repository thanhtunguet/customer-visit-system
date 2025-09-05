#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")"/../.. && pwd)
cd "$ROOT_DIR/apps/worker"

python3 -m venv .venv || true
source .venv/bin/activate
python -m pip install --upgrade pip >/dev/null
pip install -r requirements.txt >/dev/null || true

# Load environment variables from .env file if it exists, preserving existing ones
if [ -f .env ]; then
    echo "Loading environment variables from .env file..."
    # Store existing environment variables that we want to preserve
    EXISTING_WORKER_ID=${WORKER_ID:-}
    
    set -o allexport
    source .env
    set +o allexport
    
    # Restore command-line environment variables if they were set
    if [ -n "$EXISTING_WORKER_ID" ]; then
        export WORKER_ID="$EXISTING_WORKER_ID"
        echo "Preserving command-line WORKER_ID: $WORKER_ID"
    fi
fi

export API_URL=${API_URL:-http://localhost:8080}
export TENANT_ID=${TENANT_ID:-t-dev}
export SITE_ID=${SITE_ID:-s-1}
export CAMERA_ID=${CAMERA_ID:-c-1}
export WORKER_API_KEY=${WORKER_API_KEY:-dev-api-key}

echo "Starting worker-sim against $API_URL"
exec .venv/bin/python -m app.main

