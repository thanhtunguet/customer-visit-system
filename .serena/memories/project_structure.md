# Project Structure

## Repository Layout (Monorepo)
```
/
├── apps/
│   ├── api/                  # FastAPI backend service
│   │   ├── app/             # Main application code
│   │   │   ├── core/        # Core functionality (database, auth, etc.)
│   │   │   ├── models/      # Database models
│   │   │   ├── routers/     # API route handlers
│   │   │   ├── services/    # Business logic services
│   │   │   ├── enums/       # Enumeration definitions
│   │   │   ├── main.py      # FastAPI app entry point
│   │   │   └── schemas.py   # Pydantic models
│   │   ├── tests/           # API service tests
│   │   ├── alembic/         # Database migration files
│   │   ├── db/              # Database utilities and scripts
│   │   ├── tools/           # Development tools
│   │   ├── requirements.txt # Python dependencies
│   │   ├── .env.example     # Environment template
│   │   └── Dockerfile       # Container definition
│   ├── worker/              # Face recognition worker service
│   │   ├── app/             # Worker application code
│   │   ├── tests/           # Worker service tests
│   │   ├── requirements.txt # Worker dependencies
│   │   ├── .env.example     # Environment template
│   │   └── Dockerfile       # Container definition
│   └── web/                 # React frontend application
│       ├── src/             # React source code
│       ├── package.json     # Node.js dependencies
│       ├── .env.example     # Environment template
│       └── Dockerfile       # Container definition
├── packages/
│   ├── python/
│   │   └── common/          # Shared Python utilities and models
│   └── ts/
│       └── common/          # Shared TypeScript types
├── contracts/               # JSON Schema definitions
├── infra/
│   ├── compose/             # Docker Compose configurations
│   └── k8s/                 # Kubernetes manifests
│       ├── base/            # Base Kubernetes resources
│       └── overlays/        # Environment-specific overlays
├── scripts/
│   ├── dev/                 # Development helper scripts
│   ├── prod/                # Production deployment scripts
│   └── e2e_demo.sh         # End-to-end test script
├── docs/                    # Documentation files
├── tasks/                   # Task management files
├── Makefile                 # Build and development commands
├── pyproject.toml          # Python project configuration
├── CLAUDE.md               # Project instructions for Claude
└── README.md               # Project documentation
```

## Key File Purposes

### API Service Structure
- `app/main.py` - FastAPI application factory and configuration
- `app/core/database.py` - Database connection and session management
- `app/models/database.py` - SQLAlchemy ORM models
- `app/schemas.py` - Pydantic request/response models
- `app/routers/` - API endpoint implementations
- `app/services/` - Business logic and external service integrations

### Worker Service Structure
- `app/main.py` - Worker entry point and configuration
- `app/services/` - Face detection, embedding, and camera services
- `app/models/` - Worker-specific data models

### Infrastructure Files
- `infra/compose/docker-compose.dev.yml` - Local development services
- `infra/k8s/` - Production Kubernetes deployment manifests
- `scripts/dev/` - Development server startup scripts

### Configuration Files
- `.env.example` files - Environment variable templates
- `requirements.txt` - Python dependency specifications
- `package.json` - Node.js dependency specifications
- `alembic.ini` - Database migration configuration