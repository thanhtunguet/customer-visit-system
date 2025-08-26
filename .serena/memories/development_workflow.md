# Development Workflow

## Daily Development Process

### Setup and Environment
1. **External Services Required** (macOS Development):
   - PostgreSQL Server (v13+) 
   - Milvus Vector Database (v2.3+)
   - MinIO Object Storage
   - Configure connection details in .env files

2. **Service Startup Order**:
   ```bash
   # Terminal 1: API Service (start first)
   make api-dev

   # Terminal 2: Worker Service (after API is running)
   make worker-dev  

   # Terminal 3: Web Interface
   make web-dev
   ```

### Development Standards

#### Code Changes Workflow
1. **Before Changes**: Understand existing patterns and conventions
2. **Implementation**: Follow established code style and patterns
3. **Testing**: Write/update tests for new functionality
4. **Validation**: Run quality checks before committing

#### Required Quality Gates
```bash
make fmt                     # Code formatting
make test                    # All service tests
make e2e                     # Integration tests
```

#### Database Schema Changes
```bash
cd apps/api
alembic revision --autogenerate -m "description"
alembic upgrade head
```

## Project Characteristics

### Multi-tenant Architecture
- **Tenant Isolation**: Row Level Security (RLS) enforces data separation
- **Context Setting**: JWT tokens carry tenant information
- **Partitioned Storage**: Milvus partitions and MinIO prefixes per tenant

### Face Recognition Pipeline
- **Real-time Processing**: Camera feeds → Detection → Embeddings → Recognition
- **High Performance**: Optimized for low-latency face matching
- **Configurable**: Environment-driven configuration for different deployment scenarios

### External Dependencies
- **No Internet Required**: All dependencies pre-packaged or locally available
- **External Services**: Requires separate PostgreSQL, Milvus, MinIO instances
- **Arm64 Compatible**: Supports Apple Silicon and production arm64 deployments

## Common Development Tasks

### Adding New API Endpoints
1. Define Pydantic schemas in `apps/api/app/schemas.py`
2. Implement router in `apps/api/app/routers/`
3. Add business logic in `apps/api/app/services/`
4. Write tests in `apps/api/tests/`
5. Update OpenAPI documentation: `make openapi`

### Worker Enhancements
1. Modify processing pipeline in `apps/worker/app/services/`
2. Update configuration in WorkerConfig
3. Add tests in `apps/worker/tests/`
4. Test with different camera sources (RTSP, USB)

### Frontend Features
1. Create React components in `apps/web/src/components/`
2. Add routes in routing configuration
3. Integrate with API using axios
4. Style with Tailwind CSS and Ant Design

### Database Changes
1. Create Alembic migration
2. Update SQLAlchemy models
3. Modify Pydantic schemas if needed
4. Test migration up/down operations

## Troubleshooting Common Issues

### Service Connection Problems
- Check external service availability (PostgreSQL, Milvus, MinIO)
- Verify environment variables in .env files
- Ensure proper startup order (API before Worker)

### Face Processing Issues
- Verify camera permissions and availability
- Check ONNX Runtime compatibility (especially on arm64)
- Monitor memory usage during face processing

### Multi-tenant Issues
- Verify JWT token contains correct tenant context
- Check RLS policies are active
- Ensure Milvus partitions are properly created