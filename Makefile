PY ?= python3
PIP ?= pip3

.PHONY: dev-up dev-down fmt lint test e2e buildx openapi api-dev worker-dev web-dev

dev-up:
	@echo "Docker dev-up deprecated on macOS. Use 'make api-dev' 'make web-dev' 'make worker-dev' in separate terminals."

dev-down:
	@echo "Nothing to stop in script-driven dev."

fmt:
	@echo "Formatting Python..."
	@find apps packages -name "*.py" -print0 | xargs -0 -I{} $(PY) -m black {} 2>/dev/null || true

lint:
	@echo "Lint placeholders (ruff/flake8 can be wired)"

test:
	@echo "Running API tests..."
	@cd apps/api && $(PY) -m pytest tests/ -v
	@echo "Running Worker tests..."
	@cd apps/worker && $(PY) -m pytest tests/ -v

e2e:
	bash scripts/e2e_demo.sh

buildx:
	docker buildx bake --pull --progress=plain

openapi:
	$(PY) apps/api/tools/export_openapi.py

api-dev:
	bash scripts/dev/api_dev.sh

worker-dev:
	bash scripts/dev/worker_dev.sh

web-dev:
	bash scripts/dev/web_dev.sh
