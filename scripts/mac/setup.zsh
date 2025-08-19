#!/usr/bin/env zsh
set -euo pipefail
echo "Setting up dev env (macOS)"
echo "Ensure: Docker Desktop with buildx, Python 3.11, Node 18+"
python3 -m venv .venv || true
echo "Done. Use: source .venv/bin/activate"

