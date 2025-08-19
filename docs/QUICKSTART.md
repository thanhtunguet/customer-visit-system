# Quickstart

- Prereqs: Docker, Docker Buildx, Python 3.11, Node 18+
- Monorepo layout mirrors apps, packages, contracts, infra.

Steps:
- make dev-up
- API: http://localhost:8080 (FastAPI /docs)
- Web: http://localhost:5173
- Worker-sim posts sample events.

Notes:
- Env via .env files under app folders (see examples).
- No internet at runtime; mocks included for tests.

