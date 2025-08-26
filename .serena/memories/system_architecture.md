# System Architecture

## Enhanced Architecture Overview
The system has evolved to support an enhanced worker architecture with HTTP endpoints, API delegation/proxy patterns, and distributed processing capabilities.

## Core Components

### API Service (apps/api)
- **FastAPI Backend**: REST API with tenant-aware endpoints
- **Multi-tenant RLS**: Row Level Security for data isolation
- **Authentication**: JWT (RS256) with role-based access control
- **Worker Proxy**: HTTP delegation to workers for camera operations
- **Background Jobs**: APScheduler for maintenance tasks

### Worker Service (apps/worker) - ENHANCED
- **HTTP Server**: RESTful API for camera control (when USE_ENHANCED_WORKER=true)
- **Camera Streaming**: Full OpenCV streaming service with device management
- **Multi-Camera Support**: Handle multiple camera streams simultaneously
- **Worker Communication**: Registration, heartbeat, command system
- **Face Processing Pipeline**: Detection → Landmarks → Embeddings → Recognition

### Web Interface (apps/web)
- **React Dashboard**: Real-time monitoring and analytics
- **Staff Management**: Enhanced face management with multiple images per staff
- **Camera Control**: Live monitoring and control interface
- **Multi-tenant UI**: Tenant switching and context management

## Data Layer

### PostgreSQL Database
- **Tables**: tenants, sites, cameras, staff, customers, visits, api_keys
- **RLS Policy**: Tenant isolation with `current_setting('app.tenant_id')`
- **Enhanced Tables**: staff_face_images with landmarks and embeddings
- **Audit Trail**: Created/updated timestamps, user tracking

### Milvus Vector Database
- **Collection**: face_embeddings (dim=512, metric=IP/cosine)
- **Partitions**: Per tenant_id for data isolation
- **Indexing**: IVF index for fast similarity search
- **Configuration**: Environment-driven setup

### MinIO Object Storage
- **Buckets**: faces-raw, faces-derived
- **Lifecycle**: 30-day retention on raw images
- **Security**: Signed URLs and authenticated access
- **Integration**: Direct upload/download capabilities

## Communication Patterns

### API ↔ Worker Communication
- **Registration**: Workers register with API on startup
- **Heartbeat**: 30-second status updates (IDLE, PROCESSING, ONLINE, OFFLINE, ERROR)
- **Command System**: ASSIGN_CAMERA, RELEASE_CAMERA operations
- **HTTP Proxy**: API delegates camera operations to workers
- **Conflict Management**: Device lock management across multiple workers

### Worker ↔ Camera Integration
- **Stream Management**: OpenCV-based capture from RTSP/USB
- **Frame Processing**: Configurable FPS with WORKER_FPS setting
- **Device Management**: Exclusive access with proper cleanup
- **Error Handling**: Graceful failure and recovery patterns

### Real-time Communication
- **Server-Sent Events**: Camera status updates to web interface
- **WebSocket**: Worker monitoring and live updates
- **Event Streaming**: Face detection events and visitor notifications

## Processing Pipeline

### Face Recognition Workflow
1. **Capture**: OpenCV from RTSP/USB camera feeds
2. **Detection**: YuNet (default) or RetinaFace face detection
3. **Alignment**: 5-point facial landmark detection
4. **Embedding**: InsightFace ArcFace 512-D embeddings with L2-norm
5. **Matching**: Cosine similarity search in Milvus
6. **Recognition**: Staff pre-matching and visitor identification
7. **Storage**: Event logging and image archival

### Multi-tenant Data Flow
1. **Request Context**: JWT token provides tenant context
2. **RLS Enforcement**: Database queries filtered by tenant_id
3. **Vector Partitioning**: Milvus partitions isolate tenant embeddings
4. **Object Storage**: Tenant-prefixed object keys in MinIO

## Security Architecture

### Authentication & Authorization
- **JWT Tokens**: RS256 signed tokens with role claims
- **API Keys**: Worker authentication with JWT minting
- **Role-based Access**: system_admin, tenant_admin, site_manager, worker
- **Tenant Context**: Per-request tenant isolation

### Data Security
- **Row Level Security**: PostgreSQL RLS for tenant isolation
- **Encrypted Storage**: At-rest encryption for sensitive data
- **Secure Communication**: HTTPS/TLS for all external communication
- **Audit Logging**: Comprehensive activity tracking

## Deployment Architecture

### Development Environment
- **Script-based**: Individual service startup via Make commands
- **External Dependencies**: PostgreSQL, Milvus, MinIO services
- **Hot Reload**: Development servers with auto-reload

### Production Environment
- **Kubernetes**: Container orchestration with manifests
- **Docker Images**: Multi-arch builds (arm64, amd64)
- **Service Mesh**: Network policies and ingress configuration
- **Scaling**: Horizontal Pod Autoscaling (HPA)
- **Persistence**: StatefulSets for databases, PVCs for storage