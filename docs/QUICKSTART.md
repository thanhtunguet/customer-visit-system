# Quickstart

- Prereqs: Docker, Docker Buildx, Python 3.11, Node 18+
- Monorepo layout mirrors apps, packages, contracts, infra.

Development (no Docker on macOS):
- Terminal 1: make api-dev  # runs FastAPI with reload on :8080
- Terminal 2: make web-dev  # runs Vite dev server on :5173
- Terminal 3: make worker-dev  # worker-sim posts a sample event
  - API: http://localhost:8080 (OpenAPI at /v1/openapi.json)
  - Web: http://localhost:5173

Production (systemd):
- Copy repo to server (e.g., /home/ubuntu/face-recognition)
- Create venvs and install deps under apps/api and apps/worker
- sudo bash scripts/prod/install_systemd.sh
- Edit /etc/face/face.env and start services:
  - sudo systemctl start face-api face-worker face-web

Notes:
- Env via /etc/face/face.env (prod) or shell exports (dev).
- No internet at runtime; mocks included for tests.
