# Enhanced Face Processing API Documentation

The Face Recognition API includes advanced face processing capabilities with enhanced cropping algorithms that handle various real-world scenarios including very large faces, very small faces, and multi-face images.

## Overview

The enhanced face processing system provides:
- **Adaptive cropping** for faces of varying sizes
- **Multi-face selection strategies** for choosing the best face
- **Aspect ratio preservation** to prevent distortion
- **Configurable parameters** for different use cases
- **Edge case handling** for robust operation

## Face Processing Service

### Enhanced Methods

#### `process_staff_face_image_enhanced()`
Enhanced version of staff face processing with improved cropping:

```python
result = await face_service.process_staff_face_image_enhanced(
    base64_image="data:image/jpeg;base64,/9j/4AAQSkZJRgABA...",
    tenant_id="tenant-123",
    staff_id="staff-456"
)
```

**Response includes:**
```json
{
  "success": true,
  "image_id": "uuid-string",
  "image_path": "staff-faces/tenant-123/uuid.jpg",
  "image_hash": "sha256-hash",
  "landmarks": [[x1, y1], [x2, y2], [x3, y3], [x4, y4], [x5, y5]],
  "embedding": [512 float values],
  "face_count": 2,
  "confidence": 0.85,
  "bbox": [x, y, width, height],
  "face_crop_b64": "base64-encoded-cropped-face",
  "crop_metadata": {
    "crop_strategy": "large_face",
    "total_faces": 2,
    "selection_strategy": "best_quality"
  },
  "face_quality": 0.75,
  "processing_version": "enhanced_v2"
}
```

#### `process_customer_faces_from_image_enhanced()`
Enhanced customer face processing that processes ALL detected faces:

```python
result = await face_service.process_customer_faces_from_image_enhanced(
    base64_image="data:image/jpeg;base64,/9j/4AAQSkZJRgABA...",
    tenant_id="tenant-123"
)
```

**Response includes:**
```json
{
  "success": true,
  "image_hash": "sha256-hash", 
  "faces": [
    {
      "face_index": 0,
      "landmarks": [[x1, y1], [x2, y2], [x3, y3], [x4, y4], [x5, y5]],
      "embedding": [512 float values],
      "confidence": 0.8,
      "bbox": [x, y, width, height],
      "face_crop_b64": "base64-encoded-cropped-face",
      "crop_metadata": {
        "crop_strategy": "standard",
        "face_ratio": 0.12
      },
      "face_quality": 0.7,
      "processing_version": "enhanced_v2"
    }
  ],
  "face_count": 3,
  "total_detected": 3,
  "processing_version": "enhanced_v2"
}
```

## Face Cropping Strategies

The enhanced cropping system automatically selects the appropriate strategy based on face characteristics:

### Large Face Strategy (`large_face`)
- **Trigger**: Face occupies >60% of image area (very close to camera)
- **Approach**: Conservative margin (≤5%) to preserve all facial features
- **Use case**: Person very close to webcam, face fills most of frame
- **Benefits**: Prevents cutting off parts of large faces

### Small Face Strategy (`small_face`)
- **Trigger**: Face smaller than minimum threshold (distant from camera)
- **Approach**: Expanded margin (≥25%) with additional context
- **Use case**: Person far from webcam, face is small in frame
- **Benefits**: Captures sufficient detail for recognition

### Standard Strategy (`standard`)
- **Trigger**: Normal-sized faces between thresholds
- **Approach**: Configurable margin (default 15%)
- **Use case**: Person at normal distance from camera
- **Benefits**: Optimal balance of face content and context

## Multi-Face Selection Strategies

When multiple faces are detected, the system uses configurable strategies to select the primary face:

### `best_quality` (Default)
Balances multiple factors for optimal selection:
- Detection confidence (40% weight)
- Face size optimization (30% weight) - prefers faces around 15% of image
- Landmark availability bonus (30% weight)

### `largest`
Selects the face with the largest bounding box area.
- **Best for**: Close-up scenarios where the main subject is closest to camera

### `most_centered`
Selects the face closest to the image center.
- **Best for**: Fixed camera positions where main subject is typically centered

### `highest_confidence`
Selects the face with the highest detection confidence score.
- **Best for**: Challenging lighting conditions where confidence matters most

## Configuration Parameters

Configure face cropping behavior via environment variables:

### Core Parameters
```bash
# Minimum face size threshold
API_MIN_FACE_SIZE=40

# Margin around face as percentage (0.15 = 15%)
API_CROP_MARGIN_PCT=0.15

# Target output size for cropped faces (224x224 recommended)
API_TARGET_SIZE=224

# Primary face selection strategy
API_PRIMARY_FACE_STRATEGY=best_quality

# Threshold for large face detection (0.6 = 60% of image)
API_MAX_FACE_RATIO=0.6

# Preserve aspect ratio with letterboxing
API_PRESERVE_ASPECT=true
```

### Strategy Options
- `best_quality` - Balanced approach (default)
- `largest` - Choose biggest face
- `most_centered` - Choose most centered face
- `highest_confidence` - Choose most confident detection

### Target Size Recommendations
- **224x224** - Optimal for most face recognition models (default)
- **160x160** - Smaller size for faster processing
- **112x112** - Minimal size for basic recognition
- **256x256** or higher - Higher quality for detailed analysis

## Integration Examples

### Staff Image Upload Endpoint
```python
@router.post("/staff/{staff_id}/faces")
async def upload_staff_face(
    staff_id: str,
    face_image: str,  # Base64 encoded image
    user: dict = Depends(get_current_user),
    face_service: FaceProcessingService = Depends()
):
    # Use enhanced processing
    result = await face_service.process_staff_face_image_enhanced(
        face_image, user["tenant_id"], staff_id
    )
    
    if result["success"]:
        # Store face data with enhanced metadata
        face_data = {
            "staff_id": staff_id,
            "image_path": result["image_path"],
            "landmarks": result["landmarks"],
            "embedding": result["embedding"],
            "crop_metadata": result["crop_metadata"],
            "quality_score": result["face_quality"]
        }
        # Save to database...
        
    return result
```

### Customer Face Analysis Endpoint
```python
@router.post("/customers/analyze-faces")
async def analyze_customer_faces(
    uploaded_image: str,  # Base64 encoded image
    user: dict = Depends(get_current_user),
    face_service: FaceProcessingService = Depends()
):
    # Process all faces in image
    result = await face_service.process_customer_faces_from_image_enhanced(
        uploaded_image, user["tenant_id"]
    )
    
    if result["success"]:
        # Analyze each detected face
        for face in result["faces"]:
            # Search for similar customers using embedding
            similar_customers = await search_similar_faces(
                face["embedding"], user["tenant_id"]
            )
            face["similar_customers"] = similar_customers
            
    return result
```

## Performance Considerations

### Processing Speed
- **Enhanced cropping adds ~5-10ms** per face compared to basic cropping
- **Multi-face selection** adds minimal overhead
- **Quality assessment** adds ~1-2ms per face

### Memory Usage  
- **Target size 224x224**: ~150KB per cropped face
- **Preserved originals**: Full resolution until MinIO upload
- **Embedding storage**: 512 float values (2KB) per face

### Optimization Tips
1. **Use appropriate target size**: 224x224 for quality, 160x160 for speed
2. **Configure strategy per use case**: 
   - `largest` for single-person scenarios
   - `best_quality` for mixed scenarios
   - `most_centered` for fixed cameras
3. **Disable aspect preservation** if distortion is acceptable for speed

## Error Handling

The enhanced system includes comprehensive fallback mechanisms:

### Graceful Degradation
```python
# Enhanced processing with fallback
try:
    result = await process_staff_face_image_enhanced(image, tenant, staff_id)
except Exception as e:
    logger.warning(f"Enhanced processing failed: {e}")
    # Automatically falls back to original processing
    result = await process_staff_face_image(image, tenant, staff_id)
```

### Common Issues and Solutions

#### No Faces Detected
```json
{
  "success": false,
  "error": "No faces detected in image",
  "face_count": 0,
  "suggestions": [
    "Ensure good lighting",
    "Check image quality", 
    "Verify face is clearly visible"
  ]
}
```

#### Poor Quality Images
- **Low resolution**: Increase `API_MIN_FACE_SIZE` threshold
- **Poor lighting**: Adjust detection confidence thresholds
- **Blurry images**: Enable quality-based filtering

#### Multiple Face Confusion
- **Wrong face selected**: Adjust `API_PRIMARY_FACE_STRATEGY`
- **Inconsistent selection**: Use `most_centered` for fixed scenarios
- **Quality issues**: Use `best_quality` strategy

## Testing

### Unit Tests
```bash
# Run face cropping tests
pytest apps/api/tests/test_api_face_cropping.py -v

# Run specific test scenarios
pytest apps/api/tests/test_api_face_cropping.py::test_huge_face_api_scenario -v
pytest apps/api/tests/test_api_face_cropping.py::test_multi_face_api_scenarios -v
```

### Integration Tests
```bash
# Test full face processing pipeline
pytest apps/api/tests/test_face_processing_service.py -v

# Test API endpoints
pytest apps/api/tests/test_staff_face_images.py -v
```

### Manual Testing Scenarios

1. **Large Face Test**
   - Upload image where face occupies >70% of frame
   - Verify `crop_strategy: "large_face"` in response
   - Check that no facial features are cut off

2. **Small Face Test**
   - Upload image where face is <5% of frame
   - Verify `crop_strategy: "small_face"` in response
   - Check adequate context is preserved

3. **Multi-Face Test**
   - Upload image with 3+ faces
   - Test different selection strategies
   - Verify consistent primary face selection

## Migration Guide

### Updating Existing Endpoints

To use enhanced processing in existing endpoints:

```python
# Before
result = await face_service.process_staff_face_image(image, tenant, staff_id)

# After  
result = await face_service.process_staff_face_image_enhanced(image, tenant, staff_id)

# Check for enhanced metadata
if result.get("processing_version") == "enhanced_v2":
    # Handle enhanced features
    crop_info = result.get("crop_metadata", {})
    quality_score = result.get("face_quality", 0.0)
```

### Database Schema Updates

Consider adding columns for enhanced metadata:

```sql
ALTER TABLE staff_face_images ADD COLUMN crop_metadata JSONB;
ALTER TABLE staff_face_images ADD COLUMN face_quality FLOAT;
ALTER TABLE staff_face_images ADD COLUMN processing_version VARCHAR(20);

-- Index for querying by quality
CREATE INDEX idx_staff_face_quality ON staff_face_images(face_quality);
```

### Configuration Migration

Update environment configuration:

```bash
# Add new API cropping parameters
API_MIN_FACE_SIZE=40
API_CROP_MARGIN_PCT=0.15  
API_TARGET_SIZE=224
API_PRIMARY_FACE_STRATEGY=best_quality
API_MAX_FACE_RATIO=0.6
API_PRESERVE_ASPECT=true
```

## Best Practices

1. **Choose appropriate target size**: 224x224 for production quality
2. **Configure strategy per deployment**: 
   - Security cameras: `most_centered`
   - Mobile uploads: `best_quality`
   - Kiosks: `largest`
3. **Monitor quality scores**: Set minimum thresholds for acceptance
4. **Test with real data**: Validate with actual deployment images
5. **Log crop strategies**: Monitor distribution for optimization
6. **Handle edge cases**: Plan for no-face and poor-quality scenarios

## Monitoring and Analytics

Track enhanced processing metrics:

```python
# Log crop strategy distribution
crop_strategies = ["large_face", "standard", "small_face"]
strategy_counts = {strategy: 0 for strategy in crop_strategies}

# Monitor quality distributions
quality_ranges = {
    "excellent": 0,  # > 0.8
    "good": 0,       # 0.6 - 0.8
    "fair": 0,       # 0.4 - 0.6  
    "poor": 0        # < 0.4
}

# Track selection strategy effectiveness
selection_strategies = ["best_quality", "largest", "most_centered", "highest_confidence"]
```

This enhanced face processing system provides robust, configurable face cropping that adapts to real-world scenarios and significantly improves face recognition accuracy across diverse image conditions.