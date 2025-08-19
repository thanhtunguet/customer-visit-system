# Task Completion Checklist

When completing any coding task in this project, ensure the following steps are performed:

## Code Quality Checks

### 1. Formatting
```bash
# Format Python code
make fmt
```
- Ensure all Python code is formatted with Black
- Check that imports are organized properly

### 2. Linting
```bash
# Run linting checks
make lint
```
- Address any linting issues reported
- Ensure type hints are present and correct

### 3. Testing
```bash
# Run unit tests
make test

# Run end-to-end tests (when applicable)
make e2e
```
- Ensure all existing tests pass
- Add new tests for new functionality
- Maintain ≥80% test coverage for core components

## API-Specific Tasks

### 4. OpenAPI Documentation
```bash
# Export updated OpenAPI specification
make openapi
```
- Update OpenAPI docs after API changes
- Ensure all endpoints are documented

### 5. Database Migrations
```bash
# If database schema changes were made
cd apps/api && alembic revision --autogenerate -m "description"
cd apps/api && alembic upgrade head
```

## Security & Compliance

### 6. Security Review
- Ensure Row Level Security (RLS) is properly implemented
- Verify JWT authentication is correctly applied
- Check for any hardcoded secrets or credentials

### 7. Multi-tenant Validation
- Verify tenant isolation is maintained
- Test cross-tenant access is properly blocked

## Performance & Scalability

### 8. Performance Validation
- For API changes: ensure p95 latency <300ms under load
- For database changes: verify query performance
- For worker changes: ensure real-time processing capabilities

## Documentation

### 9. Update Documentation
- Update relevant files in `/docs/` if architecture changes
- Update README if setup instructions change
- Document any new environment variables or configuration

## Final Verification

### 10. Integration Testing
```bash
# Run full integration test
make e2e
```
- Verify end-to-end functionality works
- Test with realistic data volumes when applicable

### 11. Git Hygiene
```bash
# Check status and commit
git status
git add .
git commit -m "feat: descriptive commit message"
```
- Use Conventional Commits format
- Ensure clean commit history
- Review changes before committing

## Environment-Specific Checks

### Development Environment
- Verify `make api-dev`, `make web-dev`, `make worker-dev` start successfully
- Check that hot-reload works as expected

### Production Readiness
- Ensure Docker builds succeed: `make buildx`
- Verify Kubernetes manifests are valid
- Check that environment variables have sensible defaults

## Critical Acceptance Criteria

Before considering any task complete, ensure:
- [ ] All tests pass (`make test`)
- [ ] Code is properly formatted (`make fmt`)
- [ ] No linting errors (`make lint`)
- [ ] API documentation is up-to-date (`make openapi`)
- [ ] End-to-end flow works (`make e2e`)
- [ ] Security measures are in place (RLS, JWT, etc.)
- [ ] Multi-tenant isolation is verified
- [ ] Performance requirements are met