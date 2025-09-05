# Simplified Worker Architecture - Socket-Only Communication

## Overview
The worker service has been simplified to use only the basic worker with pure socket-based communication. All enhanced worker features and HTTP server functionality have been removed for a clean, simple architecture.

## Architecture

### Before (Complex)
```
Enhanced Worker Process
├── FastAPI HTTP Server (Port 8090)
│   ├── /health endpoints
│   ├── /cameras/{id}/stream/* endpoints  
│   ├── /logs/* endpoints
│   └── Camera streaming service
├── Face Recognition Pipeline
├── Socket communication to API
└── Background tasks and monitoring
```

### After (Simplified)
```
Basic Worker Process
├── Face Recognition Pipeline
├── Socket communication to API ONLY
├── Worker registration & heartbeat
└── Clean shutdown handling
```

## Files Structure

### Removed Files
- `enhanced_worker_with_streaming.py` - Complete HTTP server implementation
- `enhanced_worker.py` - Alternative enhanced worker  
- `camera_streaming_service.py` - Camera streaming service

### Remaining Files
- `main.py` - Simple worker entry point, basic worker only
- `worker_client.py` - Socket-based communication with API
- `detectors.py` - Face detection functionality
- `embedder.py` - Face embedding functionality  
- `face_processor.py` - Face processing pipeline
- Other support files (fsm.py, worker_id_manager.py, etc.)

## Key Benefits

### 1. No Port Conflicts
- **Before**: Multiple workers competed for HTTP port 8090
- **After**: Workers only use outbound socket connections - no ports bound

### 2. Simplified Deployment  
- **Before**: Required port management, firewall rules, HTTP endpoint monitoring
- **After**: No port configuration needed, simple process monitoring

### 3. True Worker Pattern
- **Before**: Hybrid worker/server architecture with dual responsibilities
- **After**: Pure worker that processes faces and reports via socket

### 4. Resource Efficiency
- **Before**: FastAPI server overhead, HTTP request processing, streaming buffers
- **After**: Minimal overhead, direct face processing only

### 5. Easy Scaling
- **Before**: Complex HTTP proxy/load balancer setup for multiple workers
- **After**: Start multiple worker processes directly - no coordination needed

## Configuration

### Environment Variables (.env.example)
```bash
# API Configuration
API_URL=http://localhost:8080
WORKER_API_KEY=dev-secret

# Worker Identity  
WORKER_ID=worker-001

# Face Processing
DETECTOR_TYPE=yunet
EMBEDDER_TYPE=insightface
WORKER_FPS=5
CONFIDENCE_THRESHOLD=0.7

# Development/Testing
MOCK_MODE=true
```

### Removed Configuration
- ~~`USE_ENHANCED_WORKER`~~ - No longer needed, only basic worker
- ~~`WORKER_HTTP_PORT`~~ - No HTTP server to bind
- ~~Camera streaming settings~~ - Will be re-implemented via socket later

## Usage

### Starting Multiple Workers
```bash
# Terminal 1
WORKER_ID=worker-001 python -m app.main

# Terminal 2  
WORKER_ID=worker-002 python -m app.main

# Terminal 3
WORKER_ID=worker-003 python -m app.main
```

No port conflicts, no coordination needed.

### Verification
```bash
# Test worker operates without ports
python scripts/test_basic_worker.py

# Advanced port verification
python scripts/check_worker_ports.py
```

## Communication Flow

### Worker → API
```
Worker Process
    ↓ Socket Connection
API Server (Port 8080)
    ↓ HTTP/REST
Database & Services
```

### Face Processing Pipeline
```
Camera Input → Face Detection → Embedding → Staff Matching → Event Creation → API Upload
```

All communication happens via outbound socket connections from worker to API.

## Future Streaming Implementation

When camera streaming is needed, it will be implemented via:
1. **Socket-based commands** from API to worker for camera control
2. **WebSocket streams** from worker to API for frame data  
3. **API-side streaming endpoints** for frontend consumption

This maintains the pure worker pattern while enabling streaming functionality.

## Migration Benefits Summary

✅ **Multiple workers** can run simultaneously without conflicts  
✅ **Simplified deployment** - no port management needed  
✅ **Clean architecture** - workers are pure workers  
✅ **Resource efficient** - no HTTP server overhead  
✅ **Easy monitoring** - simple process-based monitoring  
✅ **Socket-only communication** - verified by test scripts  

The worker service is now properly architected as a pure worker with socket-based communication only.