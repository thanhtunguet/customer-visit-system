# Project Overview

## Purpose
Customer Visits System - A multi-tenant face recognition system with real-time monitoring, visitor analytics, and secure data management.

## Key Features
- Real-time face detection from RTSP/USB camera feeds
- Multi-tenant architecture with Row Level Security (RLS)
- Staff identification and visitor tracking
- Visitor analytics and reporting
- Secure JWT-based authentication
- Enhanced worker architecture with HTTP endpoints and proxy
- Staff face management with multiple images per staff

## System Components
- **API Service** (`/apps/api`): FastAPI backend with tenant-aware REST endpoints
- **Worker Service** (`/apps/worker`): Real-time face detection and processing from camera feeds
- **Web Interface** (`/apps/web`): React dashboard for monitoring and analytics
- **Shared Libraries** (`/packages`): Common code and type definitions
- **Contracts** (`/contracts`): JSON Schema definitions for data models
- **Infrastructure** (`/infra`): Docker Compose and Kubernetes configurations

## Architecture
- **Database**: PostgreSQL with Row Level Security (RLS)
- **Vector Database**: Milvus for face embeddings storage and similarity search
- **Object Storage**: MinIO for image storage with lifecycle management
- **Authentication**: JWT (RS256) with role-based access control
- **Face Processing**: YuNet detection, InsightFace embeddings, OpenCV capture