#!/usr/bin/env bash
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Please run as root (sudo)." >&2
  exit 1
fi

ROOT=${1:-/home/ubuntu/face-recognition}
ENV_DIR=/etc/face
mkdir -p "$ENV_DIR"
[[ -f "$ENV_DIR/face.env" ]] || cp infra/systemd/face.env.example "$ENV_DIR/face.env"

install -Dm644 infra/systemd/face-api.service /etc/systemd/system/face-api.service
install -Dm644 infra/systemd/face-worker.service /etc/systemd/system/face-worker.service
install -Dm644 infra/systemd/face-web.service /etc/systemd/system/face-web.service

systemctl daemon-reload
systemctl enable face-api face-worker face-web
echo "Edit env at $ENV_DIR/face.env then run: sudo systemctl start face-api face-worker face-web"

