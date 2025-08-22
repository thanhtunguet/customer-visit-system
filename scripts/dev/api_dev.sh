#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")"/../.. && pwd)
cd "$ROOT_DIR/apps/api"

python3 -m venv .venv || true
source .venv/bin/activate
python -m pip install --upgrade pip >/dev/null
pip install -r requirements.txt >/dev/null

export PORT=${PORT:-8080}
export ENV=${ENV:-dev}
export API_KEY_SECRET=${API_KEY_SECRET:-dev-secret}
export WORKER_API_KEY=${WORKER_API_KEY:-dev-api-key}

echo "Starting API on :$PORT (reload)"
# Use uvicorn with optimized settings for faster shutdown
exec .venv/bin/uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "$PORT" \
    --reload \
    --reload-delay 0.25 \
    --timeout-keep-alive 2

