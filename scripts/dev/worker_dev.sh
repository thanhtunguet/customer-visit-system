#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")"/../.. && pwd)
cd "$ROOT_DIR/apps/worker"

# Accept worker ID and camera index as parameters
PARAM_WORKER_ID="${1:-}"
PARAM_CAMERA_INDEX="${2:-}"

python3 -m venv .venv || true
source .venv/bin/activate
python -m pip install --upgrade pip >/dev/null
pip install -r requirements.txt >/dev/null || true

# Load environment variables from .env file if it exists
if [ -f .env ]; then
    echo "Loading environment variables from .env file..."
    set -o allexport
    source .env
    set +o allexport
fi

# Override WORKER_ID from parameter if provided
if [ -n "$PARAM_WORKER_ID" ]; then
    export WORKER_ID="$PARAM_WORKER_ID"
    echo "Using parameter WORKER_ID: $WORKER_ID"
    
    # Auto-assign camera based on worker ID for development
    case "$WORKER_ID" in
        *001|*01|*1)
            export USB_CAMERA=0
            echo "Auto-assigned USB_CAMERA=0 for worker $WORKER_ID"
            ;;
        *002|*02|*2)
            export USB_CAMERA=1
            echo "Auto-assigned USB_CAMERA=1 for worker $WORKER_ID"
            ;;
        *003|*03|*3)
            export USB_CAMERA=2
            echo "Auto-assigned USB_CAMERA=2 for worker $WORKER_ID"
            ;;
        *)
            echo "Using default USB_CAMERA setting for worker $WORKER_ID"
            ;;
    esac
elif [ -n "${WORKER_ID:-}" ]; then
    echo "Using WORKER_ID from environment/config: $WORKER_ID"
else
    echo "No WORKER_ID specified, will use auto-generated ID"
fi

# Override USB_CAMERA from parameter if provided
if [ -n "$PARAM_CAMERA_INDEX" ]; then
    export USB_CAMERA="$PARAM_CAMERA_INDEX"
    echo "Using parameter USB_CAMERA: $USB_CAMERA"
fi

export API_URL=${API_URL:-http://localhost:8080}
export TENANT_ID=${TENANT_ID:-t-dev}
export SITE_ID=${SITE_ID:-s-1}
export CAMERA_ID=${CAMERA_ID:-c-1}
export WORKER_API_KEY=${WORKER_API_KEY:-dev-api-key}

echo "Starting worker-sim against $API_URL"
exec .venv/bin/python -m app.main

