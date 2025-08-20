# Face Recognition System - Architecture & Development Patterns

## Project Structure
```
/apps/api          # FastAPI backend
/apps/worker       # Face detection worker
/apps/web          # React TypeScript frontend
/packages/python/common  # Shared Python models
/packages/ts/common     # Shared TypeScript types
/contracts         # JSON Schemas
/infra/compose     # Docker development environment
/infra/k8s         # Kubernetes manifests
```

## Technology Stack

### Backend (API)
- **Framework**: FastAPI with Python 3.11
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Vector DB**: Milvus for face embeddings
- **Storage**: MinIO for image storage
- **Auth**: JWT with RS256, multi-role support
- **Migrations**: Alembic for database versioning

### Frontend (Web)
- **Framework**: React 18 with TypeScript
- **Build Tool**: Vite
- **UI Library**: Ant Design + Tailwind CSS
- **State Management**: React hooks + API client
- **Routing**: React Router with role-based access

### Infrastructure
- **Containerization**: Docker with multi-arch support (amd64, arm64)
- **Development**: Docker Compose for local setup
- **Production**: Kubernetes manifests with Kustomize

## Development Patterns

### Database Design
- **Multi-tenancy**: Shared schema with Row Level Security (RLS)
- **Primary Keys**: Composite keys with tenant_id for isolation
- **Foreign Keys**: Proper cascade relationships
- **Indexing**: Strategic indexes for query performance
- **Migrations**: Version-controlled with Alembic

### API Design
- **RESTful**: Standard HTTP methods with proper status codes
- **Validation**: Pydantic models for request/response validation
- **Error Handling**: Consistent error responses with proper HTTP codes
- **Authentication**: Middleware for JWT validation and tenant context
- **Documentation**: Auto-generated OpenAPI/Swagger docs

### Frontend Patterns
- **Component Structure**: Page components + reusable UI components
- **Type Safety**: Strict TypeScript with shared interface definitions
- **Form Handling**: Ant Design forms with validation
- **API Integration**: Centralized API client with error handling
- **State Management**: Local state with React hooks, no global state library needed

### Code Organization
- **Separation of Concerns**: Clear boundaries between API, business logic, and data layers
- **Shared Types**: Common interfaces between frontend and backend
- **Configuration**: Environment-based config with sensible defaults
- **Error Handling**: Consistent patterns across all layers

## Key Implementation Decisions

### Multi-tenant Architecture
- **Strategy**: Shared database with RLS for data isolation
- **Benefits**: Cost-effective, easier maintenance
- **Security**: Tenant context enforced at middleware level
- **Scalability**: Horizontal scaling through database partitioning

### ID Strategy
- **Staff/Customer IDs**: BigInteger for performance and compatibility
- **Other IDs**: String-based UUIDs for flexibility
- **Migration**: Backward-compatible conversion strategy

### Camera Support
- **Types**: Enum-based (RTSP, WEBCAM) for type safety
- **Configuration**: Dynamic validation based on camera type
- **Extensibility**: Easy to add new camera types

### Face Recognition Pipeline
- **Detection**: YuNet (default) or RetinaFace (optional)
- **Embedding**: InsightFace ArcFace 512-dimensional vectors
- **Storage**: Milvus for vector similarity search
- **Matching**: Cosine similarity with configurable thresholds

## Development Workflow

### Local Development
1. **Environment Setup**: Docker Compose for infrastructure
2. **API Development**: FastAPI with hot reload
3. **Frontend Development**: Vite dev server with HMR
4. **Database**: PostgreSQL with Alembic migrations
5. **Testing**: Unit tests + integration tests + e2e tests

### Code Quality
- **Linting**: Consistent code formatting and style
- **Type Checking**: Full TypeScript coverage
- **Testing**: Minimum 80% coverage requirement
- **Documentation**: Code comments and API documentation

### Deployment Strategy
- **Containerization**: Multi-stage Dockerfiles for optimization
- **Orchestration**: Kubernetes with proper resource limits
- **Monitoring**: Health checks and metrics collection
- **Security**: Secrets management and network policies

## Best Practices Established

### Database
- Always use tenant_id in WHERE clauses
- Proper foreign key constraints with cascade rules
- Strategic indexing for query performance
- Version-controlled migrations

### API
- Consistent error response format
- Proper HTTP status codes
- Request/response validation
- Tenant context in all operations

### Frontend
- Type-safe API calls
- Consistent form validation
- Proper error handling and user feedback
- Responsive design with Tailwind CSS

### Security
- JWT-based authentication
- Role-based authorization
- Input validation and sanitization
- Secure file upload handling