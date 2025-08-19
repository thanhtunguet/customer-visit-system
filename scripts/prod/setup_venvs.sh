#!/usr/bin/env bash
set -euo pipefail
ROOT=${1:-$(pwd)}

echo "Setting up venv for API..."
python3 -m venv "$ROOT/apps/api/.venv" || true
"$ROOT/apps/api/.venv/bin/python" -m pip install --upgrade pip
"$ROOT/apps/api/.venv/bin/pip" install -r "$ROOT/apps/api/requirements.txt"

echo "Setting up venv for Worker..."
python3 -m venv "$ROOT/apps/worker/.venv" || true
"$ROOT/apps/worker/.venv/bin/python" -m pip install --upgrade pip
"$ROOT/apps/worker/.venv/bin/pip" install -r "$ROOT/apps/worker/requirements.txt" || true

echo "Done."

