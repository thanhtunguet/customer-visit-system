# Face Recognition System - Project Overview

## Purpose
A multi-tenant face recognition system with real-time monitoring, visitor analytics, and secure data management. The system processes camera feeds to identify staff and track visitors using face detection and recognition technology.

## Architecture
- **Multi-tenant**: Shared schema with Row Level Security (RLS)
- **Real-time**: Live camera feed processing and visitor tracking
- **Secure**: JWT-based authentication with role-based access control
- **Scalable**: Designed for production deployment with Kubernetes

## Tech Stack

### Backend
- **Python 3.11** with FastAPI for REST API
- **PostgreSQL** with Row Level Security for multi-tenant data
- **Milvus** vector database for face embedding search
- **MinIO** for object storage (images)
- **Alembic** for database migrations

### Frontend
- **React 18** with TypeScript
- **Vite** for build tooling
- **Ant Design** for UI components
- **Tailwind CSS** for styling

### Infrastructure
- **Docker & Docker Compose** for local development
- **Kubernetes** for production deployment
- **systemd** services for Mac Mini worker deployment

### Face Recognition Stack
- **OpenCV** for camera capture
- **YuNet/RetinaFace** for face detection
- **InsightFace ArcFace** for face embeddings (512-D)
- **ONNX Runtime** for inference (arm64 compatible)

## Repository Structure
```
/apps/
  /api/          - FastAPI backend service
  /worker/       - Face detection worker service
  /web/          - React frontend
/packages/
  /python/common/ - Shared Python models and utilities
  /ts/common/    - Shared TypeScript types
/contracts/      - JSON Schema definitions
/infra/
  /compose/      - Docker Compose configurations
  /k8s/          - Kubernetes manifests
  /systemd/      - systemd service files
/scripts/        - Development and deployment scripts
/docs/           - Documentation and runbooks
```

## Key Features
- Real-time face detection from RTSP/USB cameras
- Staff vs visitor identification
- Visitor analytics and reporting
- Multi-tenant architecture with data isolation
- 30-day image retention policy
- RESTful API with OpenAPI documentation
- Web dashboard for monitoring and management