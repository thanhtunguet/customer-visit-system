# Project Structure

The project is organized into a monorepo structure with distinct applications and shared packages.

- `apps/`: Contains the main application services.
  - `api/`: The FastAPI backend service.
    - `app/`: Core application logic, including routers, services, and models.
    - `alembic/`: Database migration scripts.
    - `tests/`: Pytest tests for the API.
    - `Dockerfile`: Containerization script for the API.
  - `worker/`: The face recognition worker service.
    - `app/`: Core worker logic.
    - `tests/`: Pytest tests for the worker.
    - `Dockerfile`: Containerization script for the worker.
  - `web/`: The React-based frontend application.
    - `src/`: Source code for the React app, including components, pages, and services.
    - `vite.config.ts`: Vite configuration.
    - `package.json`: Frontend dependencies and scripts.
- `packages/`: Shared code used across different applications.
  - `python/common/`: Common Python utilities and data structures.
  - `ts/common/`: Common TypeScript types and functions.
- `contracts/`: JSON schema definitions for data models, ensuring data consistency across services.
- `infra/`: Infrastructure as Code.
  - `compose/`: Docker Compose files for development environments.
  - `k8s/`: Kubernetes manifests for production deployments.
- `scripts/`: Utility and automation scripts for development and operations.
- `Makefile`: Provides a convenient set of commands for common development tasks like running, testing, and formatting the code.
