# Suggested Commands

## Development Setup Commands

### API Service Development
```bash
make api-dev                    # Start API development server (port 8080)
cd apps/api && source .venv/bin/activate  # Activate API virtual environment
```

### Worker Service Development  
```bash
make worker-dev                 # Start worker development service
cd apps/worker && source .venv/bin/activate  # Activate worker virtual environment
```

### Web Interface Development
```bash
make web-dev                    # Start web development server (auto-detects npm/yarn/pnpm)
cd apps/web && npm run dev      # Alternative: direct web development
```

## Database Management
```bash
cd apps/api
alembic upgrade head           # Run database migrations
alembic revision --autogenerate -m "description"  # Create new migration
alembic current               # Show current migration
```

## Testing Commands
```bash
make test                     # Run all tests (API + Worker)
cd apps/api && python -m pytest tests/ -v     # Run API tests only
cd apps/worker && python -m pytest tests/ -v  # Run worker tests only
make e2e                      # Run end-to-end integration tests
```

## Code Quality Commands
```bash
make fmt                      # Format Python code with black
make lint                     # Run linting (placeholder for ruff/flake8)
```

## Build and Deploy Commands
```bash
make buildx                   # Build multi-arch Docker images
make openapi                  # Export OpenAPI specification
```

## Utility Commands (macOS/Darwin)
```bash
# Standard Unix commands work on macOS
ls -la                        # List files with details
find . -name "*.py"          # Find Python files
grep -r "pattern" apps/      # Search for patterns
cd /path/to/directory        # Change directory

# macOS specific (if available)
gtimeout 30 command          # Timeout command (GNU coreutils)
```

## Bootstrap and Setup Commands
```bash
python apps/api/create_admin.py              # Create admin user
python apps/api/create_worker_api_key.py     # Create worker API key
python apps/api/bootstrap_worker_setup.py    # Bootstrap worker setup
```

## Environment Configuration
```bash
cp apps/api/.env.example apps/api/.env       # Setup API environment
cp apps/worker/.env.example apps/worker/.env # Setup worker environment  
cp apps/web/.env.example apps/web/.env       # Setup web environment
```

## External Service Commands
```bash
# PostgreSQL
pg_isready -h localhost -p 5432              # Check PostgreSQL status
psql -h localhost -p 5432 -U postgres -d facedb  # Connect to database

# MinIO (if minio client installed)
mc config host add myminio http://localhost:9000 ACCESS_KEY SECRET_KEY
mc admin info myminio                         # Check MinIO status

# Health checks
curl http://localhost:8080/health            # Check API health
```