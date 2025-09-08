# Face Recognition Worker

This worker processes camera streams to detect and recognize faces, recording customer visits and filtering out staff members.

## Features

- **Face Detection**: YuNet detector with Haar Cascade fallback
- **Face Recognition**: InsightFace ArcFace embeddings (512-dimensional)
- **Staff Pre-matching**: Local staff filtering to avoid unnecessary API calls
- **Camera Support**: RTSP streams and USB cameras
- **Resilient Processing**: Automatic retry logic and failed event queuing
- **Configurable**: Environment-based configuration system

## Configuration

Set these environment variables:

### Required
- `WORKER_API_KEY`: API key for authentication
- `TENANT_ID`: Tenant identifier
- `SITE_ID`: Site identifier
- `CAMERA_ID`: Camera identifier

### Camera Configuration
- `RTSP_URL`: RTSP stream URL (takes priority over USB)
- `USB_CAMERA`: USB camera device index (default: 0)
- `FRAME_WIDTH`: Camera frame width (default: 640)
- `FRAME_HEIGHT`: Camera frame height (default: 480)

### Processing Configuration
- `DETECTOR_TYPE`: Face detector (yunet, mock) (default: yunet)
- `EMBEDDER_TYPE`: Face embedder (insightface, mock) (default: insightface)
- `WORKER_FPS`: Processing frame rate (default: 5)
- `CONFIDENCE_THRESHOLD`: Face detection confidence (default: 0.7)
- `STAFF_MATCH_THRESHOLD`: Staff matching similarity (default: 0.8)

### Enhanced Face Cropping Configuration
- `MIN_FACE_SIZE`: Minimum face size in pixels for processing (default: 40)
- `CROP_MARGIN_PCT`: Margin around face as percentage, e.g., 0.15 = 15% (default: 0.15)
- `TARGET_SIZE`: Target output size for cropped faces in pixels (default: 224)
- `PRIMARY_FACE_STRATEGY`: Strategy for selecting primary face when multiple detected (default: best_quality)
  - `best_quality`: Balance of confidence, size, landmarks, and detector quality
  - `largest`: Choose the largest face by area
  - `most_centered`: Choose face closest to image center
  - `highest_confidence`: Choose face with highest detection confidence
- `MAX_FACE_RATIO`: Maximum face-to-frame ratio before special large-face handling (default: 0.6)
- `PRESERVE_ASPECT`: Preserve aspect ratio with letterboxing, true/false (default: true)

### API Configuration
- `API_URL`: Face recognition API endpoint (default: http://localhost:8080)
- `MAX_API_RETRIES`: Max API call retries (default: 3)
- `FAILED_EVENT_RETRY_INTERVAL`: Retry interval for failed events in seconds (default: 30)

### Other
- `MOCK_MODE`: Use mock components for testing (default: true)
- `LOG_LEVEL`: Logging level (default: INFO)

## Running

### Development/Testing
```bash
# Mock mode (no real camera or ML models)
export MOCK_MODE=true
export DETECTOR_TYPE=mock
export EMBEDDER_TYPE=mock
python -m app.main
```

### Production with USB Camera
```bash
export MOCK_MODE=false
export USB_CAMERA=0
export DETECTOR_TYPE=yunet
export EMBEDDER_TYPE=insightface
export WORKER_API_KEY=your-api-key
export TENANT_ID=your-tenant
export SITE_ID=your-site
export CAMERA_ID=your-camera
python -m app.main
```

### Production with RTSP Camera
```bash
export MOCK_MODE=false
export RTSP_URL=rtsp://camera.local/stream
export DETECTOR_TYPE=yunet
export EMBEDDER_TYPE=insightface
export WORKER_API_KEY=your-api-key
export TENANT_ID=your-tenant
export SITE_ID=your-site
export CAMERA_ID=your-camera
python -m app.main
```

## Docker

```bash
# Build image
docker build -t face-recognition-worker .

# Run with environment file
docker run --env-file .env face-recognition-worker

# Run with USB camera (requires privileged access)
docker run --privileged -v /dev:/dev --env-file .env face-recognition-worker
```

## Architecture

### Enhanced Face Detection Pipeline
1. **Frame Capture**: Captures frames from camera at configured FPS
2. **Face Detection**: Multi-detector system with YuNet, MTCNN, RetinaFace, MediaPipe, OpenCV DNN, and Haar Cascade fallbacks
3. **Face Cropping**: Enhanced cropping algorithm that adapts to face size and position:
   - **Large faces** (>60% of frame): Conservative cropping to preserve all features
   - **Small faces** (<min size): Expanded cropping with additional context
   - **Normal faces**: Standard cropping with configurable margin
   - **Edge handling**: Safe cropping for faces near frame boundaries
   - **Multi-face selection**: Configurable strategies for choosing primary face
4. **Face Alignment**: Aligns faces using 5-point landmarks when available
5. **Canonical Sizing**: Resizes to target size (default 224x224) with aspect ratio preservation
6. **Embedding Generation**: Creates 512-dim embeddings using InsightFace ArcFace
7. **Staff Filtering**: Checks against local staff embeddings first
8. **API Submission**: Sends face events to API for customer matching and visit recording

### Face Cropping Strategies

The enhanced face cropping system handles various real-world scenarios:

#### Large Face Handling (Close to Camera)
- **Scenario**: Face occupies >60% of frame (very close to camera)
- **Strategy**: Uses conservative margin (≤5%) to avoid cutting off facial features
- **Benefits**: Ensures complete face capture even when subject is very close

#### Small Face Handling (Far from Camera) 
- **Scenario**: Face smaller than minimum size threshold (far from camera)
- **Strategy**: Uses expanded margin (≥25%) to capture sufficient context
- **Benefits**: Provides enough detail for recognition even with distant subjects

#### Multi-Face Selection Strategies
- **best_quality**: Balances confidence, size, landmarks, and detector quality (default)
- **largest**: Selects the largest face by area
- **most_centered**: Selects face closest to image center  
- **highest_confidence**: Selects face with highest detection confidence

#### Aspect Ratio Preservation
- **Enabled** (default): Maintains original face proportions with letterboxing
- **Disabled**: Stretches face to fill target square, may cause distortion

### Error Handling
- **Camera Failures**: Automatic reconnection with exponential backoff
- **API Failures**: Exponential backoff retry with event queuing
- **Processing Errors**: Graceful error handling with continued operation

### Performance Considerations
- **Frame Skipping**: Processes at configured FPS to balance accuracy and performance  
- **Staff Pre-filtering**: Reduces API calls by filtering known staff locally
- **Asynchronous Processing**: Non-blocking I/O for API calls
- **Memory Management**: Efficient frame processing without accumulation

## Dependencies

- opencv-python: Camera capture and basic computer vision
- insightface: Face recognition and embedding generation
- httpx: Async HTTP client for API communication
- pydantic: Data validation and serialization
- numpy: Numerical operations

## Testing

```bash
# Run basic functionality test
python test_worker_basic.py

# Run full test suite
pytest tests/ -v

# Run specific test categories
pytest tests/test_detectors.py -v
pytest tests/test_embedder.py -v  
pytest tests/test_face_recognition_pipeline.py -v
pytest tests/test_face_cropping.py -v  # New enhanced cropping tests
```

### Face Cropping Test Coverage

The test suite includes comprehensive coverage for various face cropping scenarios:

- **Huge faces**: >80% of frame (webcam very close)
- **Tiny faces**: <5% of frame (webcam far away)
- **Edge cases**: Faces near frame boundaries
- **Multi-face scenarios**: Different selection strategies
- **Aspect ratio preservation**: With and without letterboxing
- **Configuration variations**: Different margins and target sizes
- **Integration tests**: End-to-end cropping pipeline

## Monitoring

The worker logs processing statistics and errors:

```
INFO - Worker initialized successfully
INFO - Camera connected successfully, processing at 5 FPS  
INFO - Processed 1 faces at 14:23:45
INFO - Matched staff member staff-123 with similarity 0.856
INFO - Face event processed successfully: person_id=c_abc123, match=new
```

## Troubleshooting

### Camera Issues
- **"Failed to open camera"**: Check camera permissions and device availability
- **Poor frame quality**: Adjust `FRAME_WIDTH`, `FRAME_HEIGHT`, and `WORKER_FPS`
- **RTSP connection fails**: Verify URL and network connectivity

### API Issues  
- **401 Authentication errors**: Check `WORKER_API_KEY` and API endpoint
- **Slow processing**: Reduce `WORKER_FPS` or check API performance
- **Events queued for retry**: Check network connectivity and API availability

### Performance Issues
- **High CPU usage**: Reduce `WORKER_FPS` or use mock mode for testing
- **Memory leaks**: Restart worker periodically in production
- **Staff matching errors**: Verify staff embeddings are properly loaded

### Face Cropping Issues
- **Faces cut off**: Increase `CROP_MARGIN_PCT` (default: 0.15)
- **Poor recognition on large faces**: Ensure `MAX_FACE_RATIO` is appropriate (default: 0.6)
- **Small faces not detected**: Decrease `MIN_FACE_SIZE` threshold (default: 40)
- **Wrong face selected**: Adjust `PRIMARY_FACE_STRATEGY` based on your scenario:
  - Use `most_centered` for fixed camera positions
  - Use `largest` for close-up scenarios
  - Use `highest_confidence` for challenging lighting
  - Use `best_quality` for balanced performance (default)
- **Distorted faces**: Enable `PRESERVE_ASPECT=true` for better quality (default)

## Production Deployment

For production deployment:

1. Use appropriate hardware with sufficient CPU/GPU for ML processing
2. Set up proper logging aggregation and monitoring
3. Configure automatic restarts on failure
4. Use environment-specific configuration
5. Monitor API response times and error rates
6. Set up alerts for camera disconnections and processing failures