# Customer Visits System - Deployment Guide

## Prerequisites

- Python 3.11+
- PostgreSQL 12+
- Milvus 2.4+ (for vector storage)
- MinIO (for image storage)
- Docker & Docker Compose (optional, for containerized deployment)

## Dependencies Installation

### Option 1: Production Environment

1. **Create and activate virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install API dependencies:**
   ```bash
   cd apps/api
   pip install -r requirements.txt
   ```

3. **Install Worker dependencies:**
   ```bash
   cd ../worker
   pip install -r requirements.txt
   ```

4. **Install common package:**
   ```bash
   cd ../../packages/python/common
   pip install -e .
   ```

### Option 2: Docker Deployment

```bash
# Build and start all services
docker-compose -f infra/compose/docker-compose.dev.yml up --build
```

## Required Dependencies for Face Processing

The face recognition enhancement requires these specific packages:

```txt
# Core face processing
Pillow==10.4.0          # Image processing
opencv-python==4.10.0.84 # Computer vision
numpy==1.26.4           # Numerical computing

# API framework
fastapi==0.111.0
uvicorn==0.30.0
pydantic==2.7.1

# Database
sqlalchemy==2.0.30
asyncpg==0.29.0
alembic==1.13.2

# Vector database
pymilvus==2.4.5

# Object storage
minio==7.2.7

# Authentication
PyJWT==2.8.0
```

## Environment Configuration

Create `.env` files in both `apps/api/` and `apps/worker/` directories:

### apps/api/.env
```env
DATABASE_URL=postgresql://user:password@localhost:5432/customer_visits_db
MILVUS_URI=localhost:19530
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
JWT_SECRET_KEY=your-secret-key-here
```

### apps/worker/.env
```env
API_URL=http://localhost:8080
API_KEY=your-worker-api-key
CAMERA_TYPE=WEBCAM
DEVICE_INDEX=0
```

## Database Setup

1. **Run migrations:**
   ```bash
   cd apps/api
   alembic upgrade head
   ```

2. **Verify migration status:**
   ```bash
   alembic current
   # Should show: 004_staff_face_images (head)
   ```

## Verification

### Check Service Status

1. **Face Processing Dependencies:**
   ```bash
   curl http://localhost:8080/v1/health/face-processing
   ```
   Expected response:
   ```json
   {
     "face_processing_available": true,
     "status": "ready",
     "message": "Face processing is ready"
   }
   ```

2. **Milvus Connection:**
   ```bash
   curl http://localhost:8080/v1/health/milvus
   ```

3. **Overall Health:**
   ```bash
   curl http://localhost:8080/v1/health
   ```

### Test Face Image Upload

1. **Create a test staff member:**
   ```bash
   curl -X POST http://localhost:8080/v1/staff \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -d '{"name": "Test User", "site_id": null}'
   ```

2. **Upload face image:**
   ```bash
   curl -X POST http://localhost:8080/v1/staff/STAFF_ID/faces \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -d '{"image_data": "data:image/jpeg;base64,BASE64_IMAGE_DATA", "is_primary": true}'
   ```

## Troubleshooting

### Common Issues

1. **"No module named 'PIL'"**
   - Install Pillow: `pip install Pillow==10.4.0`

2. **"No module named 'cv2'"**
   - Install OpenCV: `pip install opencv-python==4.10.0.84`

3. **Face processing not available**
   - Check dependencies are installed in the correct virtual environment
   - Verify with: `python -c "import cv2, numpy, PIL; print('All dependencies available')"`

4. **Database connection errors**
   - Ensure PostgreSQL is running
   - Verify connection string in .env file
   - Check database exists and user has permissions

5. **Milvus connection errors**
   - Start Milvus service
   - Check MILVUS_URI in environment variables
   - Verify Milvus is accepting connections

### Development Mode

For development without full dependencies:

1. **The system gracefully degrades** - API will start but face processing features will be disabled
2. **Check status endpoint** to verify which features are available
3. **Mock implementations** are used for missing services (Milvus, MinIO)

### Production Deployment Checklist

- [ ] All dependencies installed and verified
- [ ] Database migrations applied
- [ ] Environment variables configured
- [ ] Milvus vector database running
- [ ] MinIO object storage running
- [ ] SSL certificates configured (production)
- [ ] Firewall rules configured
- [ ] Backup strategy in place
- [ ] Monitoring and logging configured

## Performance Considerations

### Face Processing
- **Memory Usage**: ~500MB for OpenCV and face models
- **Processing Time**: ~200-500ms per image depending on size
- **Concurrent Processing**: Limited by CPU cores

### Storage Requirements
- **Database**: Metadata and embeddings (~2KB per face image)
- **MinIO**: Raw images (~50-500KB per image)
- **Milvus**: Vector embeddings (~2KB per embedding)

### Recommended Hardware
- **Minimum**: 4GB RAM, 2 CPU cores, 10GB storage
- **Recommended**: 8GB RAM, 4 CPU cores, 50GB storage
- **Production**: 16GB RAM, 8 CPU cores, 100GB+ storage

## Security Notes

1. **API Keys**: Generate strong API keys for worker authentication
2. **JWT Secrets**: Use cryptographically secure secrets
3. **Database**: Use connection pooling and prepared statements
4. **File Upload**: Images are validated and size-limited
5. **Network**: Use HTTPS in production
6. **Access Control**: Implement proper role-based permissions

## Monitoring

Key metrics to monitor:
- API response times (target: <300ms p95)
- Face processing success rate
- Storage usage (MinIO, Milvus)
- Database query performance
- Memory and CPU usage

## Support

For issues with the face recognition enhancement:
1. Check the health endpoints first
2. Verify all dependencies are correctly installed
3. Review logs for specific error messages
4. Ensure proper environment configuration