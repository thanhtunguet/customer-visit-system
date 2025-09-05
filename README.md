# Customer Visits System

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

## Development Setup

### Prerequisites

This system requires external services for production-like development on macOS:
- **PostgreSQL Server** (v13+)
- **Milvus Vector Database** (v2.3+)
- **MinIO Object Storage** (compatible with S3 API)

### Environment Configuration

Each service requires environment configuration through `.env` files:

#### 1. API Service Configuration

```bash
cd apps/api
cp .env.example .env
```

Edit `apps/api/.env` with your external service endpoints:

```bash
# Database Configuration (External PostgreSQL Server)
DB_HOST=your-postgres-server.example.com
DB_PORT=5432
DB_USER=your-db-user
DB_PASSWORD=your-db-password
DB_NAME=facedb

# Milvus Configuration (External Milvus Server)
MILVUS_HOST=your-milvus-server.example.com
MILVUS_PORT=19530

# MinIO Configuration (External MinIO Server)
MINIO_ENDPOINT=your-minio-server.example.com:9000
MINIO_ACCESS_KEY=your-access-key
MINIO_SECRET_KEY=your-secret-key
```

#### 2. Worker Service Configuration

```bash
cd apps/worker
cp .env.example .env
```

Edit `apps/worker/.env`:

```bash
# Point to your local API service
API_URL=http://localhost:8080
WORKER_API_KEY=dev-api-key

# Configure your camera source
RTSP_URL=rtsp://admin:password@192.168.1.100:554/stream
# OR for USB camera:
USB_CAMERA=0
```

#### 3. Web Interface Configuration

```bash
cd apps/web  
cp .env.example .env
```

Edit `apps/web/.env` if API runs on different port:

```bash
VITE_API_URL=http://localhost:8080
```

### Database Setup

Before first run, initialize the database schema:

```bash
cd apps/api
# Install dependencies
pip install -r requirements.txt

# Run database migrations  
alembic upgrade head
```

### Running Services

#### Start Individual Services:

```bash
# Terminal 1: API Service
cd apps/api
python -m uvicorn app.main:app --reload --port 8080

# Terminal 2: Worker Service (after API is running)
cd apps/worker  
python app/main.py

# Terminal 3: Web Interface
cd apps/web
npm run dev
```

#### Or use Make commands:

```bash
# Start API service
make api-dev

# Start web interface  
make web-dev

# Start single worker (uses camera 0 by default)
make worker-dev

# Start multiple workers with different IDs and cameras
make worker-dev W=worker-001        # Auto-assigns camera 0 (USB webcam)
make worker-dev W=worker-002        # Auto-assigns camera 1 (built-in webcam)
make worker-dev W=worker-003        # Auto-assigns camera 2 (if available)

# Manually specify worker ID and camera
make worker-dev W=worker-001 C=0    # Worker-001 using camera 0
make worker-dev W=worker-002 C=1    # Worker-002 using camera 1

# Run tests
make test

# Run end-to-end tests
make e2e
```

### Multiple Worker Development

For development and testing with multiple cameras on the same machine:

#### Quick Start - Two Workers with Two Cameras

```bash
# Terminal 1: Start API
make api-dev

# Terminal 2: Start web interface  
make web-dev

# Terminal 3: Start first worker (USB webcam)
make worker-dev W=worker-001

# Terminal 4: Start second worker (built-in webcam)
make worker-dev W=worker-002
```

#### Worker Auto-Assignment Rules

The system automatically assigns cameras based on worker ID patterns:

- **worker-001**, **worker-01**, **worker-1** → Camera 0 (typically USB webcam)
- **worker-002**, **worker-02**, **worker-2** → Camera 1 (typically built-in webcam)  
- **worker-003**, **worker-03**, **worker-3** → Camera 2 (additional camera if available)

#### Manual Camera Assignment

Override automatic assignment with explicit camera index:

```bash
# Force specific worker-camera combinations
make worker-dev W=worker-alice C=0     # Alice uses USB webcam
make worker-dev W=worker-bob C=1       # Bob uses built-in webcam
make worker-dev W=worker-charlie C=2   # Charlie uses external camera
```

#### Camera Device Detection

To see available cameras on your system:

```bash
# macOS: List video devices
system_profiler SPCameraDataType

# Linux: List video devices  
v4l2-ctl --list-devices

# Test camera access with OpenCV (Python)
python3 -c "import cv2; print([i for i in range(10) if cv2.VideoCapture(i).isOpened()])"
```

#### Worker Monitoring

Once workers are running, monitor them in:

1. **Web Interface**: `http://localhost:3000/workers`
   - View worker status, streaming indicators, camera assignments
   - Real-time updates via WebSocket
   
2. **API Endpoints**:
   ```bash
   # List all workers
   curl http://localhost:8080/v1/workers
   
   # Get specific worker status
   curl http://localhost:8080/v1/workers/{worker-id}
   ```

3. **Worker Logs**: Check terminal output for camera connection status

### Troubleshooting

#### Connection Issues

1. **PostgreSQL Connection Failed**
   - Verify DB_HOST, DB_PORT, and credentials
   - Ensure PostgreSQL accepts connections from your IP
   - Check firewall rules

2. **Milvus Connection Failed**
   - Verify MILVUS_HOST and MILVUS_PORT
   - Ensure Milvus service is running and accessible
   - Check Milvus logs for authentication issues

3. **MinIO Connection Failed**
   - Verify MINIO_ENDPOINT format (host:port)
   - Check MINIO_ACCESS_KEY and MINIO_SECRET_KEY
   - Ensure MinIO API is accessible (try curl test)

#### Service Health Checks

```bash
# Check API service health
curl http://localhost:8080/health

# Check if external services are reachable
# PostgreSQL
pg_isready -h your-postgres-server.example.com -p 5432

# MinIO (if minio client installed)
mc config host add myminio http://your-minio-server.example.com:9000 ACCESS_KEY SECRET_KEY
mc admin info myminio
```

### Environment Variables Reference

#### API Service Variables

| Variable                    | Description                         | Default           | Required   |
| --------------------------- | ----------------------------------- | ----------------- | ---------- |
| `APP_NAME`                  | Application name                    | `face-api`        | No         |
| `ENV`                       | Environment (dev/prod)              | `dev`             | No         |
| `HOST`                      | Bind host                           | `0.0.0.0`         | No         |
| `PORT`                      | Bind port                           | `8080`            | No         |
| `JWT_ISSUER`                | JWT token issuer                    | `face.local`      | No         |
| `JWT_AUDIENCE`              | JWT token audience                  | `face`            | No         |
| `JWT_PRIVATE_KEY`           | RSA private key for JWT signing     | -                 | Yes (prod) |
| `JWT_PUBLIC_KEY`            | RSA public key for JWT verification | -                 | Yes (prod) |
| `API_KEY_SECRET`            | Secret for API key generation       | `dev-secret`      | Yes        |
| `DB_HOST`                   | PostgreSQL host                     | `localhost`       | Yes        |
| `DB_PORT`                   | PostgreSQL port                     | `5432`            | No         |
| `DB_USER`                   | PostgreSQL username                 | `postgres`        | Yes        |
| `DB_PASSWORD`               | PostgreSQL password                 | `postgres`        | Yes        |
| `DB_NAME`                   | PostgreSQL database name            | `facedb`          | Yes        |
| `DATABASE_URL`              | Full PostgreSQL connection string   | Auto-generated    | No         |
| `MILVUS_HOST`               | Milvus vector database host         | `localhost`       | Yes        |
| `MILVUS_PORT`               | Milvus port                         | `19530`           | No         |
| `MILVUS_COLLECTION`         | Milvus collection name              | `face_embeddings` | No         |
| `MINIO_ENDPOINT`            | MinIO endpoint (host:port)          | `localhost:9000`  | Yes        |
| `MINIO_ACCESS_KEY`          | MinIO access key                    | `minioadmin`      | Yes        |
| `MINIO_SECRET_KEY`          | MinIO secret key                    | `minioadmin`      | Yes        |
| `MINIO_BUCKET_RAW`          | Raw images bucket                   | `faces-raw`       | No         |
| `MINIO_BUCKET_DERIVED`      | Processed images bucket             | `faces-derived`   | No         |
| `TENANT_HEADER`             | HTTP header for tenant ID           | `X-Tenant-ID`     | No         |
| `FACE_SIMILARITY_THRESHOLD` | Face matching threshold (0.0-1.0)   | `0.6`             | No         |
| `MAX_FACE_RESULTS`          | Max results from face search        | `5`               | No         |

#### Worker Service Variables

| Variable               | Description                           | Default           | Required |
| ---------------------- | ------------------------------------- | ----------------- | -------- |
| `API_URL`              | API service endpoint                  | `http://api:8080` | Yes      |
| `TENANT_ID`            | Worker tenant identifier              | `t-dev`           | Yes      |
| `SITE_ID`              | Site identifier                       | `s-1`             | Yes      |
| `CAMERA_ID`            | Camera identifier                     | `c-1`             | Yes      |
| `WORKER_API_KEY`       | API authentication key                | `dev-api-key`     | Yes      |
| `DETECTOR_TYPE`        | Face detector (`yunet`, `mock`)       | `yunet`           | No       |
| `EMBEDDER_TYPE`        | Face embedder (`insightface`, `mock`) | `insightface`     | No       |
| `WORKER_FPS`           | Processing frame rate                 | `5`               | No       |
| `RTSP_URL`             | RTSP camera stream URL                | -                 | No       |
| `USB_CAMERA`           | USB camera device index               | `0`               | No       |
| `CONFIDENCE_THRESHOLD` | Detection confidence threshold        | `0.7`             | No       |
| `MOCK_MODE`            | Enable mock mode for testing          | `true`            | No       |

#### Web Service Variables

| Variable       | Description                       | Default                 | Required |
| -------------- | --------------------------------- | ----------------------- | -------- |
| `VITE_API_URL` | API service endpoint for frontend | `http://localhost:8080` | Yes      |

## Deployment

- Docker Compose for local development
- Kubernetes manifests for production deployment