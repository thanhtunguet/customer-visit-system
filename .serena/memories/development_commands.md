# Development Commands - Quick Reference

## 🚀 Starting Services

### API Service
```bash
cd apps/api
source .venv/bin/activate
python -m app.main
# Or use: make api-dev
# Access: http://localhost:8080/v1/health
```

### Web Frontend  
```bash
cd apps/web
npm install
npm run dev
# Or use: make web-dev
# Access: http://localhost:5173
```

### Worker Service
```bash
cd apps/worker
source .venv/bin/activate
python -m app.main
# Or use: make worker-dev
# Runs in mock mode by default
```

## 🔧 Development Workflow

### Package Management
```bash
# Install API dependencies
cd apps/api && pip install -r requirements.txt

# Install shared packages as editable
cd apps/api && pip install -e ../../packages/python/common/

# Install web dependencies
cd apps/web && npm install
```

### Code Quality
```bash
make fmt     # Format Python code with Black
make lint    # Run linting checks  
make test    # Run unit tests
make e2e     # Run end-to-end tests
```

### Database Operations
```bash
cd apps/api
source .venv/bin/activate

# Create migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Check migration status
alembic current
```

## 🧪 Testing Commands

### Unit Tests
```bash
# API tests
cd apps/api && python -m pytest tests/ -v

# Worker tests  
cd apps/worker && python -m pytest tests/ -v

# All tests
make test
```

### Integration Testing
```bash
# Manual API testing
curl http://localhost:8080/v1/health

# Get JWT token
curl -X POST http://localhost:8080/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{"grant_type": "api_key", "api_key": "dev-api-key", "tenant_id": "t-dev", "role": "tenant_admin"}'

# Test protected endpoint
curl -H "Authorization: Bearer <token>" http://localhost:8080/v1/me
```

### E2E Demo
```bash
# Full system demo
bash scripts/e2e_demo.sh

# Or use shorthand
make e2e
```

## 🐳 Docker & Infrastructure

### Local Development
```bash
# Start all services with Docker Compose
docker-compose -f infra/compose/docker-compose.dev.yml up -d

# View logs
docker-compose -f infra/compose/docker-compose.dev.yml logs -f

# Stop services
docker-compose -f infra/compose/docker-compose.dev.yml down
```

### Building Images
```bash
# Build all images
make buildx

# Build specific service
docker build -t face-api apps/api/
docker build -t face-worker apps/worker/  
docker build -t face-web apps/web/
```

## 🔍 Debugging & Monitoring

### Service Health Checks
```bash
# API health
curl http://localhost:8080/v1/health

# Web app
curl http://localhost:5173

# Check service logs
docker-compose logs api
docker-compose logs worker
docker-compose logs web
```

### Database Debugging
```bash
# Connect to PostgreSQL
psql postgresql://postgres:postgres@localhost:5432/facedb

# Check RLS policies
\d+ customers
SELECT * FROM pg_policies WHERE tablename = 'customers';
```

### Mock Services Status
- **Milvus**: Mock implementation active (no real connection needed)
- **MinIO**: Mock implementation active (no real connection needed)
- **Face Detection**: Mock detector provides deterministic results
- **Embeddings**: Mock embedder provides normalized 512-D vectors

## 📝 Configuration

### Environment Variables
```bash
# API Service
export ENV=dev
export PORT=8080
export DB_HOST=localhost
export MILVUS_HOST=localhost  
export MINIO_ENDPOINT=localhost:9000
export WORKER_API_KEY=dev-api-key

# Worker Service  
export API_URL=http://localhost:8080
export TENANT_ID=t-dev
export MOCK_MODE=true
export DETECTOR_TYPE=mock
export EMBEDDER_TYPE=mock
```

### Key Files
- `apps/api/app/core/config.py` - API configuration
- `apps/api/requirements.txt` - Python dependencies
- `apps/web/package.json` - Node.js dependencies
- `infra/compose/docker-compose.dev.yml` - Docker services

## 🚨 Troubleshooting

### Common Issues & Solutions
1. **ImportError: No module named 'pkg_common'**
   ```bash
   cd apps/api && pip install -e ../../packages/python/common/
   ```

2. **Milvus connection errors**  
   - Mock implementation is active, no action needed
   - For production: Ensure Milvus service is running

3. **MinIO connection errors**
   - Mock implementation is active, no action needed  
   - For production: Ensure MinIO service is running

4. **Port conflicts**
   ```bash
   # Kill processes using ports
   lsof -ti:8080 | xargs kill -9
   lsof -ti:5173 | xargs kill -9
   ```

5. **Database connection issues**
   ```bash
   # Start PostgreSQL locally or via Docker
   docker run --name postgres -e POSTGRES_PASSWORD=postgres -p 5432:5432 -d postgres:16-alpine
   ```

## ✨ Quick Start Checklist

- [ ] Clone repository
- [ ] Install Python 3.11+ and Node.js 18+
- [ ] Run `cd apps/api && pip install -r requirements.txt`
- [ ] Run `cd apps/api && pip install -e ../../packages/python/common/`
- [ ] Run `cd apps/web && npm install`
- [ ] Start API: `make api-dev`
- [ ] Start Web: `make web-dev` 
- [ ] Test health: `curl http://localhost:8080/v1/health`
- [ ] Access UI: http://localhost:5173

The system is ready for development with mock services! 🎉