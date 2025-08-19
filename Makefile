PY ?= python3
PIP ?= pip3

.PHONY: dev-up dev-down fmt lint test e2e buildx openapi

dev-up:
	docker compose -f infra/compose/docker-compose.dev.yml up -d --build

dev-down:
	docker compose -f infra/compose/docker-compose.dev.yml down -v

fmt:
	@echo "Formatting Python..."
	@find apps packages -name "*.py" -print0 | xargs -0 -I{} $(PY) -m black {} 2>/dev/null || true

lint:
	@echo "Lint placeholders (ruff/flake8 can be wired)"

test:
	$(PY) -m pytest -q

e2e:
	bash scripts/e2e_demo.sh

buildx:
	docker buildx bake --pull --progress=plain

openapi:
	$(PY) apps/api/tools/export_openapi.py

