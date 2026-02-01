# Camera Processing Migration: API → Worker

## Overview

Successfully migrated all camera processing (streaming and face recognition) from API to Workers, implementing a delegation and proxy architecture.

## Migration Summary

### Before (API-Centric)
```
Frontend → API → Direct Camera Streaming
API → Direct Face Recognition
API → Database Events
```

### After (Worker-Centric)
```
Frontend → API → Worker (proxy) → Camera Streaming  
Worker → Face Recognition → API (events) → Database
Frontend ← API ← Worker (proxy) ← Video Stream
```

## Implementation Details

### 1. Worker Enhancements

**New Files:**
- `apps/worker/app/camera_streaming_service.py` - Full OpenCV streaming with device management
- `apps/worker/app/enhanced_worker_with_streaming.py` - Integrated worker with HTTP endpoints

**Key Features:**
- **Camera Streaming**: Complete OpenCV capture with device conflict management
- **Face Processing**: Real-time detection + embedding generation
- **Event Reporting**: Automatic face events sent to API
- **HTTP Endpoints**: RESTful API for camera control
- **Worker Registration**: Auto-discovery and assignment by API

### 2. API Delegation Layer

**New Files:**
- `apps/api/app/services/camera_proxy_service.py` - Proxy service for worker delegation

**Enhanced Services:**
- `camera_delegation_service.py` - Camera-to-worker assignment logic
- `worker_registry.py` - Worker discovery and health monitoring
- `worker_command_service.py` - Command dispatch to workers

**Key Features:**
- **Proxy Streaming**: MJPEG streams proxied from workers to frontend
- **Command Delegation**: Camera operations sent to appropriate workers
- **Health Monitoring**: Automatic cleanup of failed worker assignments
- **Load Balancing**: Automatic camera assignment to available workers

### 3. Updated API Endpoints

**Modified Routes:**
- `POST /cameras/{id}/stream/start` - Now delegates to worker
- `POST /cameras/{id}/stream/stop` - Now delegates to worker  
- `GET /cameras/{id}/stream/status` - Proxies from worker
- `GET /cameras/{id}/stream/feed` - Proxies MJPEG stream
- `GET /streaming/debug` - Shows worker streaming status

## Communication Flow

### 1. Camera Assignment
```
1. Worker registers with API → Worker Registry
2. API assigns available camera → Camera Delegation Service
3. API sends ASSIGN_CAMERA command → Worker Command Service
4. Worker starts streaming → Camera Streaming Service
5. Worker reports status → Worker Client (heartbeat)
```

### 2. Video Streaming  
```
1. Frontend requests stream → API Camera Router
2. API finds assigned worker → Camera Proxy Service
3. API proxies stream from worker → HTTP proxy
4. Worker streams MJPEG → Enhanced Worker HTTP
```

### 3. Face Recognition
```
1. Worker captures frames → Camera Streaming Service  
2. Worker detects faces → Face Processor (callback)
3. Worker generates embeddings → InsightFace/YuNet
4. Worker sends events → API Events endpoint
5. API processes events → Database + Milvus
```

## Configuration

### Worker Environment Variables
```bash
# Enhanced worker mode (default: enabled)
USE_ENHANCED_WORKER=true

# Worker HTTP server port
WORKER_HTTP_PORT=8090

# Existing variables remain the same
API_URL=http://localhost:8080
TENANT_ID=t-dev
SITE_ID=1
WORKER_API_KEY=dev-api-key
```

### API Configuration  
- Camera Proxy Service automatically initialized
- Original streaming service replaced with proxy
- Worker delegation enabled by default

## Benefits

### 1. **Scalability**
- Multiple workers can handle different cameras
- Workers can run on different machines (distributed)
- API freed from intensive camera processing

### 2. **Reliability**  
- Worker failures don't affect API
- Automatic failover and reassignment
- Independent restarts and updates

### 3. **Performance**
- Dedicated resources for camera processing
- Reduced API resource usage
- Better frame rate and streaming quality

### 4. **Flexibility**
- Workers can be specialized (different models, hardware)
- Easy to add new camera types or processing
- Independent scaling of API vs workers

## Testing

### Test Scripts
```bash
# Test enhanced worker
cd apps/worker
python test_enhanced_worker_streaming.py

# Test API proxy
cd apps/api  
python test_camera_proxy.py

# Integration test
cd apps/api
python -m pytest tests/test_camera_proxy_integration.py
```

### Manual Testing
1. Start API with proxy service
2. Start worker with enhanced mode
3. Create camera via API
4. Start streaming via API (delegates to worker)
5. Access stream via API (proxied from worker)
6. Verify face events in database

## Rollback Plan

To rollback to API-centric streaming:
1. Set `USE_ENHANCED_WORKER=false` on workers
2. Revert camera router imports to `streaming_service`  
3. Re-enable direct streaming in API main.py
4. Restart services

## Next Steps

1. **Production Testing**: Test under load with multiple cameras
2. **Monitoring**: Add metrics for worker health and performance
3. **Load Balancing**: Implement intelligent camera assignment
4. **Fault Tolerance**: Add worker failover mechanisms
5. **Security**: Add authentication for worker HTTP endpoints

## Files Changed

### New Files
- `apps/worker/app/camera_streaming_service.py`
- `apps/worker/app/enhanced_worker_with_streaming.py` 
- `apps/api/app/services/camera_proxy_service.py`
- Test scripts and documentation

### Modified Files
- `apps/api/app/routers/cameras.py` - Updated to use proxy
- `apps/api/app/main.py` - Initialize proxy service
- `apps/worker/app/main.py` - Enhanced worker option
- `apps/worker/app/worker_client.py` - Command callbacks

### Dependencies
- FastAPI for worker HTTP server
- httpx for API-worker communication
- OpenCV for camera processing (moved to worker)
- Existing face recognition pipeline unchanged