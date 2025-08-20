# Face Recognition System - Development Commands & Setup

## Essential Development Commands

### Database Operations
```bash
# Run database migrations
cd apps/api && alembic upgrade head

# Create new migration
cd apps/api && alembic revision --autogenerate -m "description"

# Check migration status
cd apps/api && alembic current

# Rollback migration
cd apps/api && alembic downgrade -1
```

### API Development
```bash
# Start API server
cd apps/api && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run API tests
cd apps/api && python -m pytest

# Check API health
curl http://localhost:8000/health

# View API documentation
open http://localhost:8000/docs
```

### Frontend Development
```bash
# Install dependencies
cd apps/web && npm install

# Start development server
cd apps/web && npm run dev

# Build for production
cd apps/web && npm run build

# Run type checking
cd apps/web && npm run type-check

# Run linting
cd apps/web && npm run lint
```

### Docker Development Environment
```bash
# Start all services
cd infra/compose && docker compose -f docker-compose.dev.yml up -d

# Start specific service
cd infra/compose && docker compose -f docker-compose.dev.yml up -d postgres

# View logs
cd infra/compose && docker compose -f docker-compose.dev.yml logs -f api

# Stop services
cd infra/compose && docker compose -f docker-compose.dev.yml down

# Rebuild images
cd infra/compose && docker compose -f docker-compose.dev.yml build
```

## Environment Configuration

### API Environment (.env)
```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/face_recognition
POSTGRES_USER=face_recognition_user
POSTGRES_PASSWORD=dev_password_123
POSTGRES_DB=face_recognition

# Milvus
MILVUS_HOST=localhost
MILVUS_PORT=19530
MILVUS_USER=root
MILVUS_PASSWORD=Milvus

# MinIO
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_SECURE=false

# JWT
JWT_SECRET_KEY=your-secret-key-here
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=1440

# API
API_PREFIX=/v1
CORS_ORIGINS=["http://localhost:3000","http://localhost:5173"]
```

### Web Environment (.env)
```bash
VITE_API_BASE_URL=http://localhost:8000
VITE_APP_TITLE=Face Recognition System
```

## Troubleshooting Common Issues

### Database Connection Issues
```bash
# Check if PostgreSQL is running
docker ps | grep postgres

# Connect to database directly
psql postgresql://user:password@localhost:5432/face_recognition

# Reset database
cd infra/compose && docker compose down -v && docker compose up -d postgres
```

### Migration Issues
```bash
# Check current schema
cd apps/api && alembic show current

# Force migration to head
cd apps/api && alembic stamp head

# Create manual migration
cd apps/api && alembic revision -m "manual_fix"
```

### API Issues
```bash
# Check API logs
cd apps/api && tail -f app.log

# Test API endpoints
curl -X GET http://localhost:8000/v1/tenants

# Debug mode
cd apps/api && uvicorn app.main:app --reload --log-level debug
```

### Frontend Issues
```bash
# Clear node modules and reinstall
cd apps/web && rm -rf node_modules package-lock.json && npm install

# Check TypeScript errors
cd apps/web && npx tsc --noEmit

# Build and serve
cd apps/web && npm run build && npm run preview
```

## Testing Commands

### Backend Tests
```bash
# Run all tests
cd apps/api && python -m pytest -v

# Run specific test file
cd apps/api && python -m pytest tests/test_api.py -v

# Run with coverage
cd apps/api && python -m pytest --cov=app --cov-report=html

# Run integration tests
cd apps/api && python -m pytest tests/integration/ -v
```

### Frontend Tests
```bash
# Run unit tests
cd apps/web && npm run test

# Run e2e tests
cd apps/web && npm run test:e2e

# Run tests with coverage
cd apps/web && npm run test:coverage
```

### End-to-End Testing
```bash
# Start all services and run e2e tests
make e2e

# Run specific e2e scenario
cd tests/e2e && python test_face_recognition_flow.py
```

## Useful Development Queries

### Database Queries
```sql
-- Check tenant data
SELECT * FROM tenants;

-- Check site configuration
SELECT t.name as tenant, s.name as site, s.site_id 
FROM tenants t JOIN sites s ON t.tenant_id = s.tenant_id;

-- Check camera configuration
SELECT c.name, c.camera_type, c.rtsp_url, c.device_index, c.is_active
FROM cameras c JOIN sites s ON c.tenant_id = s.tenant_id AND c.site_id = s.site_id;

-- Check staff and customer counts
SELECT 
  (SELECT COUNT(*) FROM staff WHERE tenant_id = 't-dev') as staff_count,
  (SELECT COUNT(*) FROM customers WHERE tenant_id = 't-dev') as customer_count;

-- Recent visits
SELECT v.timestamp, v.person_type, v.person_id, v.confidence_score
FROM visits v 
WHERE v.tenant_id = 't-dev'
ORDER BY v.timestamp DESC 
LIMIT 10;
```

## Performance Monitoring

### API Performance
```bash
# Monitor API requests
curl -X GET http://localhost:8000/metrics

# Check database connections
SELECT * FROM pg_stat_activity WHERE datname = 'face_recognition';

# Monitor Milvus performance
# Access Milvus admin at http://localhost:9001
```

### System Resources
```bash
# Monitor Docker containers
docker stats

# Check disk usage
df -h

# Monitor memory usage
free -h

# Check CPU usage
top -o %CPU
```