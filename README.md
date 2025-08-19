# Face Recognition System

A multi-tenant face recognition system with real-time monitoring, visitor analytics, and secure data management.

## System Components

- **API Service** (`/apps/api`): FastAPI backend with tenant-aware REST endpoints
- **Worker Service** (`/apps/worker`): Real-time face detection and processing from camera feeds
- **Web Interface** (`/apps/web`): React dashboard for monitoring and analytics
- **Shared Libraries** (`/packages`): Common code and type definitions
- **Contracts** (`/contracts`): JSON Schema definitions for data models
- **Infrastructure** (`/infra`): Docker Compose and Kubernetes configurations

## Features

- Real-time face detection from RTSP/USB camera feeds
- Multi-tenant architecture with Row Level Security (RLS)
- Staff identification and visitor tracking
- Visitor analytics and reporting
- Secure JWT-based authentication
- Scalable architecture with PostgreSQL, Milvus, and MinIO

## Development

```bash
# Start development environment
make dev-up

# Run tests
make test

# Run end-to-end tests
make e2e
```

## Deployment

- Docker Compose for local development
- Kubernetes manifests for production deployment