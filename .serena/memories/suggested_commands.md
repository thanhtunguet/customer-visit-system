# Suggested Commands for Face Recognition System

## Development Commands

### Start Services (Development)
```bash
# Start API service (port 8080)
make api-dev

# Start web frontend (port 5173)
make web-dev

# Start worker service
make worker-dev
```

### Code Quality
```bash
# Format Python code
make fmt

# Run linting
make lint

# Run tests
make test

# Run end-to-end tests
make e2e
```

### Docker & Build
```bash
# Build multi-arch Docker images
make buildx

# Export OpenAPI specification
make openapi
```

### Database
```bash
# Run database migrations
cd apps/api && alembic upgrade head

# Create new migration
cd apps/api && alembic revision --autogenerate -m "description"
```

### Package Management
```bash
# Python packages (API/Worker)
cd apps/api && source .venv/bin/activate && pip install -r requirements.txt

# Node packages (Web)
cd apps/web && npm install  # or yarn/pnpm
```

## System Commands (macOS/Darwin)

### Basic File Operations
```bash
ls -la          # List files with details
find . -name    # Find files by name
grep -r         # Search in files recursively
cd              # Change directory
pwd             # Print working directory
```

### Process Management
```bash
ps aux          # List running processes
kill -9 <pid>   # Force kill process
lsof -i :<port> # List processes using port
```

### Git Operations
```bash
git status      # Check repository status
git add .       # Stage all changes
git commit -m   # Commit changes
git push        # Push to remote
git pull        # Pull from remote
```

### Network & Services
```bash
netstat -an     # List network connections
curl            # Make HTTP requests
ping            # Test connectivity
```

## Testing Commands

### Unit Tests
```bash
# Run API tests
cd apps/api && python -m pytest

# Run worker tests
cd apps/worker && python -m pytest
```

### Integration Tests
```bash
# Full end-to-end test
make e2e

# Test with specific scenarios
bash scripts/e2e_demo.sh
```

## Deployment Commands

### Local Development
```bash
# Setup development environment
make dev-up

# Teardown development environment
make dev-down
```

### Production Setup (Mac Mini)
```bash
# Setup Mac Mini for worker deployment
bash scripts/mac/setup.zsh

# Install systemd services
bash scripts/prod/install_systemd.sh
```