# Task Completion Checklist

## When Task is Completed - Required Steps

### 1. Code Quality Checks
```bash
make fmt                      # Format code with black
make lint                     # Run linting (when configured)
```

### 2. Testing Requirements
```bash
make test                     # Run all tests (API + Worker)
# Individual service tests:
cd apps/api && python -m pytest tests/ -v
cd apps/worker && python -m pytest tests/ -v
```

### 3. Database Migration Checks (if schema changes)
```bash
cd apps/api
alembic upgrade head          # Ensure migrations are applied
alembic current              # Verify current migration state
```

### 4. Integration Testing
```bash
make e2e                     # Run end-to-end tests
bash scripts/e2e_demo.sh    # Alternative E2E test script
```

### 5. Service Health Verification
```bash
# Check API service health
curl http://localhost:8080/health

# Verify database connectivity (if API is running)
# Check logs for any connection errors
```

### 6. Build Verification (if Docker changes)
```bash
make buildx                  # Verify multi-arch Docker builds
```

### 7. Documentation Updates (if needed)
- Update API documentation if endpoints changed
- Update README.md if setup process changed
- Export OpenAPI spec: `make openapi`

## Production Checklist (Additional)

### Environment Validation
- Verify all required environment variables are set
- Check external service connectivity (PostgreSQL, Milvus, MinIO)
- Validate authentication and authorization flows

### Security Checks
- Ensure no secrets in code
- Verify RLS (Row Level Security) is functioning
- Test multi-tenant isolation
- Validate JWT token handling

### Performance Validation
- Run load tests if critical path changes
- Monitor memory usage during face processing
- Verify Milvus query performance

## Code Review Requirements
- All tests passing (80%+ coverage target)
- Type hints present for new Python code
- Proper error handling implemented
- Security best practices followed
- Database queries optimized
- Async/await patterns used correctly

## Deployment Requirements
- Kubernetes manifests updated (if infra changes)
- Docker images built and tested
- Environment configs validated
- Migration scripts tested