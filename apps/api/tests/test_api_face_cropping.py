"""
Unit tests for enhanced API face cropping functionality

Tests various scenarios:
- Very large faces (close to camera) 
- Very small faces (far from camera)
- Multiple faces with different selection strategies
- Edge cases (faces near frame boundaries)
- Staff and customer face processing integration
- API service integration
"""

import pytest
import numpy as np
import cv2
import os
import base64
import io
from unittest.mock import patch, MagicMock, AsyncMock
from PIL import Image

from app.services.face_cropper import FaceCropper, PrimaryFaceStrategy, api_face_cropper
from app.services.face_processing_service import FaceProcessingService


class TestApiFaceCropper:
    """Test suite for API FaceCropper class"""
    
    @pytest.fixture
    def sample_image(self):
        """Create a sample 640x480 RGB image"""
        return np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    
    @pytest.fixture  
    def large_face(self):
        """Face that occupies most of the frame"""
        return {
            'bbox': [50, 50, 540, 380],  # ~70% of 640x480 image
            'confidence': 0.9,
            'landmarks': [[150, 150], [490, 150], [320, 250], [200, 350], [440, 350]]
        }
    
    @pytest.fixture
    def small_face(self):
        """Very small face"""
        return {
            'bbox': [300, 200, 30, 40],  # Small 30x40 face
            'confidence': 0.8,
            'landmarks': None
        }
    
    def test_api_initialization_default_values(self):
        """Test API FaceCropper initialization with default values"""
        cropper = FaceCropper()
        
        assert cropper.min_face_size == 40
        assert cropper.crop_margin_pct == 0.15
        assert cropper.target_size == 224
        assert cropper.primary_face_strategy == PrimaryFaceStrategy.BEST_QUALITY
        assert cropper.max_face_ratio == 0.6
        assert cropper.preserve_aspect == True
    
    @patch.dict(os.environ, {
        'API_MIN_FACE_SIZE': '50',
        'API_CROP_MARGIN_PCT': '0.2',
        'API_TARGET_SIZE': '160',
        'API_PRIMARY_FACE_STRATEGY': 'largest',
        'API_MAX_FACE_RATIO': '0.7',
        'API_PRESERVE_ASPECT': 'false'
    })
    def test_api_initialization_from_env(self):
        """Test API FaceCropper initialization from environment variables"""
        cropper = FaceCropper()
        
        assert cropper.min_face_size == 50
        assert cropper.crop_margin_pct == 0.2
        assert cropper.target_size == 160
        assert cropper.primary_face_strategy == PrimaryFaceStrategy.LARGEST
        assert cropper.max_face_ratio == 0.7
        assert cropper.preserve_aspect == False
    
    def test_api_crop_large_face(self, sample_image, large_face):
        """Test cropping a very large face through API"""
        result = api_face_cropper.crop_face(sample_image, large_face, debug=True)
        
        assert result['crop_strategy'] == 'large_face'
        assert result['face_ratio'] > api_face_cropper.max_face_ratio
        assert 'cropped_face' in result
        assert result['cropped_face'].shape == (api_face_cropper.target_size, api_face_cropper.target_size, 3)
    
    def test_api_crop_small_face(self, sample_image, small_face):
        """Test cropping a very small face through API"""
        result = api_face_cropper.crop_face(sample_image, small_face, debug=True)
        
        assert result['crop_strategy'] == 'small_face'
        assert 'cropped_face' in result
        assert result['cropped_face'].shape == (api_face_cropper.target_size, api_face_cropper.target_size, 3)
    
    def test_global_api_instance(self):
        """Test that global API instance is properly configured"""
        assert api_face_cropper is not None
        assert isinstance(api_face_cropper, FaceCropper)
        config = api_face_cropper.get_config_info()
        assert 'min_face_size' in config
        assert 'target_size' in config


class TestFaceProcessingServiceIntegration:
    """Integration tests for face processing service with enhanced cropping"""
    
    @pytest.fixture
    def face_service(self):
        """Create a FaceProcessingService instance"""
        return FaceProcessingService()
    
    @pytest.fixture
    def sample_base64_image(self):
        """Create a sample base64 encoded image with synthetic face"""
        # Create a simple test image
        img = np.random.randint(100, 200, (400, 400, 3), dtype=np.uint8)
        
        # Draw a simple face-like pattern
        cv2.rectangle(img, (150, 150), (250, 250), (180, 180, 180), -1)  # Face
        cv2.circle(img, (180, 180), 10, (50, 50, 50), -1)  # Left eye
        cv2.circle(img, (220, 180), 10, (50, 50, 50), -1)  # Right eye
        cv2.ellipse(img, (200, 220), (15, 8), 0, 0, 180, (100, 100, 100), -1)  # Mouth
        
        # Encode to base64
        _, buffer = cv2.imencode('.jpg', img)
        img_base64 = base64.b64encode(buffer).decode('utf-8')
        return f"data:image/jpeg;base64,{img_base64}"
    
    def test_enhanced_detect_faces_and_landmarks(self, face_service, sample_base64_image):
        """Test enhanced face detection with quality assessment"""
        # Mock the face detector to return predictable results
        with patch.object(face_service, 'detect_faces_and_landmarks') as mock_detect:
            mock_detect.return_value = [
                {
                    'bbox': [150, 150, 100, 100],
                    'landmarks': [[170, 170], [230, 170], [200, 190], [180, 220], [220, 220]],
                    'confidence': 0.8
                }
            ]
            
            image = face_service.decode_base64_image(sample_base64_image)
            results = face_service._enhanced_detect_faces_and_landmarks(image)
            
            assert len(results) == 1
            assert 'area' in results[0]
            assert 'face_quality' in results[0]
            assert 'detector' in results[0]
            assert results[0]['area'] == 10000  # 100 * 100
    
    def test_assess_face_crop_quality(self, face_service):
        """Test face crop quality assessment"""
        # Create test face crops with different qualities
        
        # High quality face (good contrast, sharpness)
        good_face = np.random.randint(50, 200, (100, 100, 3), dtype=np.uint8)
        cv2.rectangle(good_face, (20, 20), (80, 80), (150, 150, 150), -1)
        quality = face_service._assess_face_crop_quality(good_face)
        assert 0.0 <= quality <= 1.0
        
        # Low quality face (very dark)
        bad_face = np.random.randint(0, 50, (100, 100, 3), dtype=np.uint8)
        quality_bad = face_service._assess_face_crop_quality(bad_face)
        assert 0.0 <= quality_bad <= 1.0
        assert quality_bad < quality  # Should be lower quality
        
        # Empty face
        empty_quality = face_service._assess_face_crop_quality(np.array([]))
        assert empty_quality == 0.0
    
    @pytest.mark.asyncio
    async def test_process_staff_face_image_enhanced(self, face_service, sample_base64_image):
        """Test enhanced staff face processing"""
        with patch.object(face_service, '_enhanced_detect_faces_and_landmarks') as mock_detect, \
             patch.object(face_service, 'upload_image_to_minio') as mock_upload, \
             patch.object(face_service, 'extract_face_embedding') as mock_embedding:
            
            # Mock face detection
            mock_detect.return_value = [
                {
                    'bbox': [150, 150, 100, 100],
                    'landmarks': [[170, 170], [230, 170], [200, 190], [180, 220], [220, 220]],
                    'confidence': 0.8,
                    'area': 10000,
                    'face_quality': 0.7,
                    'detector': 'haar'
                }
            ]
            
            # Mock MinIO upload
            mock_upload.return_value = "test-path/image.jpg"
            
            # Mock embedding generation
            mock_embedding.return_value = [0.1] * 512
            
            # Test processing
            result = await face_service.process_staff_face_image_enhanced(
                sample_base64_image, "test-tenant", "staff-123"
            )
            
            assert result['success'] == True
            assert 'crop_metadata' in result
            assert result['processing_version'] == 'enhanced_v2'
            assert result['face_count'] == 1
            assert 'face_quality' in result
    
    @pytest.mark.asyncio
    async def test_process_staff_face_image_enhanced_multi_face(self, face_service, sample_base64_image):
        """Test enhanced staff face processing with multiple faces"""
        with patch.object(face_service, '_enhanced_detect_faces_and_landmarks') as mock_detect, \
             patch.object(face_service, 'upload_image_to_minio') as mock_upload, \
             patch.object(face_service, 'extract_face_embedding') as mock_embedding:
            
            # Mock multiple face detection
            mock_detect.return_value = [
                {
                    'bbox': [100, 100, 80, 80],
                    'landmarks': [[120, 120], [160, 120], [140, 140], [125, 160], [155, 160]],
                    'confidence': 0.7,
                    'area': 6400,
                    'face_quality': 0.6,
                    'detector': 'haar'
                },
                {
                    'bbox': [250, 150, 100, 100],
                    'landmarks': [[270, 170], [330, 170], [300, 190], [280, 220], [320, 220]],
                    'confidence': 0.9,
                    'area': 10000,
                    'face_quality': 0.8,
                    'detector': 'haar'
                }
            ]
            
            mock_upload.return_value = "test-path/image.jpg"
            mock_embedding.return_value = [0.1] * 512
            
            # Test processing
            result = await face_service.process_staff_face_image_enhanced(
                sample_base64_image, "test-tenant", "staff-123"
            )
            
            assert result['success'] == True
            assert result['face_count'] == 2
            assert result['crop_metadata']['total_faces'] == 2
            assert result['crop_metadata']['selection_strategy'] in ['best_quality', 'largest', 'most_centered', 'highest_confidence']
    
    @pytest.mark.asyncio
    async def test_process_customer_faces_from_image_enhanced(self, face_service, sample_base64_image):
        """Test enhanced customer face processing"""
        with patch.object(face_service, '_enhanced_detect_faces_and_landmarks') as mock_detect, \
             patch.object(face_service, 'extract_face_embedding') as mock_embedding:
            
            # Mock face detection with multiple faces
            mock_detect.return_value = [
                {
                    'bbox': [100, 100, 80, 80],
                    'landmarks': [[120, 120], [160, 120], [140, 140], [125, 160], [155, 160]],
                    'confidence': 0.7,
                    'area': 6400,
                    'face_quality': 0.6,
                    'detector': 'haar'
                },
                {
                    'bbox': [250, 150, 100, 100],
                    'landmarks': [[270, 170], [330, 170], [300, 190], [280, 220], [320, 220]],
                    'confidence': 0.9,
                    'area': 10000,
                    'face_quality': 0.8,
                    'detector': 'haar'
                }
            ]
            
            mock_embedding.return_value = [0.1] * 512
            
            # Test processing
            result = await face_service.process_customer_faces_from_image_enhanced(
                sample_base64_image, "test-tenant"
            )
            
            assert result['success'] == True
            assert result['face_count'] == 2
            assert result['total_detected'] == 2
            assert result['processing_version'] == 'enhanced_v2'
            
            # Check that all faces were processed
            assert len(result['faces']) == 2
            for i, face in enumerate(result['faces']):
                assert face['face_index'] == i
                assert 'crop_metadata' in face
                assert 'face_quality' in face
                assert face['processing_version'] == 'enhanced_v2'
    
    @pytest.mark.asyncio
    async def test_enhanced_processing_fallback(self, face_service, sample_base64_image):
        """Test that enhanced processing falls back to original on error"""
        with patch.object(face_service, '_enhanced_detect_faces_and_landmarks', side_effect=Exception("Test error")), \
             patch.object(face_service, 'process_staff_face_image') as mock_original:
            
            mock_original.return_value = {'success': True, 'fallback': True}
            
            # Test that fallback is called
            result = await face_service.process_staff_face_image_enhanced(
                sample_base64_image, "test-tenant", "staff-123"
            )
            
            mock_original.assert_called_once()
            assert result['fallback'] == True
    
    def test_extract_face_region_enhanced(self, face_service, sample_base64_image):
        """Test enhanced face region extraction"""
        image = face_service.decode_base64_image(sample_base64_image)
        landmarks = [[170, 170], [230, 170], [200, 190], [180, 220], [220, 220]]
        
        # Test enhanced extraction
        face_region = face_service._extract_face_region(image, landmarks)
        
        assert face_region is not None
        assert face_region.shape[0] > 0
        assert face_region.shape[1] > 0
        assert len(face_region.shape) == 3  # Should be color image
    
    def test_extract_face_region_fallback(self, face_service, sample_base64_image):
        """Test face region extraction fallback when enhanced cropping fails"""
        image = face_service.decode_base64_image(sample_base64_image)
        landmarks = [[170, 170], [230, 170], [200, 190], [180, 220], [220, 220]]
        
        # Mock the enhanced cropping to fail
        with patch('app.services.face_processing_service.api_face_cropper') as mock_cropper:
            mock_cropper.crop_face.side_effect = Exception("Cropping failed")
            mock_cropper.validate_crop_result.return_value = False
            
            # Should fallback to original logic
            face_region = face_service._extract_face_region(image, landmarks)
            
            assert face_region is not None
            assert face_region.shape == (112, 112, 3)  # Fallback size


class TestApiFaceCroppingIntegration:
    """Integration tests for API face cropping with realistic scenarios"""
    
    def create_test_image_with_faces(self, face_positions: List[dict]) -> str:
        """
        Create a test image with faces at specified positions
        
        Args:
            face_positions: List of dicts with 'size_ratio', 'position', 'confidence'
        
        Returns:
            Base64 encoded image
        """
        img_h, img_w = 480, 640
        image = np.random.randint(50, 200, (img_h, img_w, 3), dtype=np.uint8)
        
        faces = []
        for i, face_spec in enumerate(face_positions):
            size_ratio = face_spec.get('size_ratio', 0.15)
            position = face_spec.get('position', 'center')
            confidence = face_spec.get('confidence', 0.8)
            
            # Calculate face size
            face_size = int(min(img_h, img_w) * size_ratio)
            
            # Position face
            if position == 'center':
                x = (img_w - face_size) // 2 + i * 50  # Offset multiple faces
                y = (img_h - face_size) // 2
            elif position == 'top_left':
                x, y = 10 + i * 30, 10
            elif position == 'bottom_right':
                x = img_w - face_size - 10 - i * 30
                y = img_h - face_size - 10
            else:
                x, y = 100 + i * 100, 100
            
            # Draw face
            cv2.rectangle(image, (x, y), (x + face_size, y + face_size), (150, 150, 150), -1)
            cv2.circle(image, (x + face_size//3, y + face_size//3), face_size//10, (50, 50, 50), -1)
            cv2.circle(image, (x + 2*face_size//3, y + face_size//3), face_size//10, (50, 50, 50), -1)
            cv2.ellipse(image, (x + face_size//2, y + 2*face_size//3), (face_size//6, face_size//8), 0, 0, 180, (100, 100, 100), -1)
            
            faces.append({
                'bbox': [x, y, face_size, face_size],
                'confidence': confidence,
                'landmarks': [
                    [x + face_size//3, y + face_size//3],
                    [x + 2*face_size//3, y + face_size//3], 
                    [x + face_size//2, y + face_size//2],
                    [x + face_size//3, y + 2*face_size//3],
                    [x + 2*face_size//3, y + 2*face_size//3]
                ]
            })
        
        # Encode to base64
        _, buffer = cv2.imencode('.jpg', image)
        img_base64 = base64.b64encode(buffer).decode('utf-8')
        return f"data:image/jpeg;base64,{img_base64}", faces
    
    @pytest.mark.asyncio
    async def test_huge_face_api_scenario(self):
        """Test API processing of huge face scenario"""
        face_service = FaceProcessingService()
        
        # Create image with very large face
        test_image, expected_faces = self.create_test_image_with_faces([
            {'size_ratio': 0.8, 'position': 'center', 'confidence': 0.9}
        ])
        
        with patch.object(face_service, '_enhanced_detect_faces_and_landmarks') as mock_detect, \
             patch.object(face_service, 'upload_image_to_minio') as mock_upload, \
             patch.object(face_service, 'extract_face_embedding') as mock_embedding:
            
            # Use the expected face data
            enhanced_face = expected_faces[0].copy()
            enhanced_face.update({
                'area': enhanced_face['bbox'][2] * enhanced_face['bbox'][3],
                'face_quality': 0.8,
                'detector': 'haar'
            })
            mock_detect.return_value = [enhanced_face]
            mock_upload.return_value = "test-path/image.jpg"
            mock_embedding.return_value = [0.1] * 512
            
            result = await face_service.process_staff_face_image_enhanced(
                test_image, "test-tenant", "staff-123"
            )
            
            assert result['success'] == True
            assert result['crop_metadata']['crop_strategy'] == 'large_face'
    
    @pytest.mark.asyncio
    async def test_tiny_face_api_scenario(self):
        """Test API processing of tiny face scenario"""
        face_service = FaceProcessingService()
        
        # Create image with very small face
        test_image, expected_faces = self.create_test_image_with_faces([
            {'size_ratio': 0.05, 'position': 'center', 'confidence': 0.7}
        ])
        
        with patch.object(face_service, '_enhanced_detect_faces_and_landmarks') as mock_detect, \
             patch.object(face_service, 'upload_image_to_minio') as mock_upload, \
             patch.object(face_service, 'extract_face_embedding') as mock_embedding:
            
            enhanced_face = expected_faces[0].copy()
            enhanced_face.update({
                'area': enhanced_face['bbox'][2] * enhanced_face['bbox'][3],
                'face_quality': 0.6,
                'detector': 'haar'
            })
            mock_detect.return_value = [enhanced_face]
            mock_upload.return_value = "test-path/image.jpg"  
            mock_embedding.return_value = [0.1] * 512
            
            result = await face_service.process_staff_face_image_enhanced(
                test_image, "test-tenant", "staff-123"
            )
            
            assert result['success'] == True
            assert result['crop_metadata']['crop_strategy'] == 'small_face'
    
    @pytest.mark.asyncio
    async def test_multi_face_api_scenarios(self):
        """Test API processing of multi-face scenarios"""
        face_service = FaceProcessingService()
        
        # Create image with multiple faces of different sizes
        test_image, expected_faces = self.create_test_image_with_faces([
            {'size_ratio': 0.2, 'position': 'center', 'confidence': 0.6},      # Medium, low confidence
            {'size_ratio': 0.15, 'position': 'top_left', 'confidence': 0.9},   # Small, high confidence
            {'size_ratio': 0.25, 'position': 'bottom_right', 'confidence': 0.7} # Large, medium confidence
        ])
        
        with patch.object(face_service, '_enhanced_detect_faces_and_landmarks') as mock_detect, \
             patch.object(face_service, 'extract_face_embedding') as mock_embedding:
            
            # Enhance face data
            enhanced_faces = []
            for face in expected_faces:
                enhanced_face = face.copy()
                enhanced_face.update({
                    'area': face['bbox'][2] * face['bbox'][3],
                    'face_quality': 0.7,
                    'detector': 'haar'
                })
                enhanced_faces.append(enhanced_face)
            
            mock_detect.return_value = enhanced_faces
            mock_embedding.return_value = [0.1] * 512
            
            # Test customer processing (processes all faces)
            result = await face_service.process_customer_faces_from_image_enhanced(
                test_image, "test-tenant"
            )
            
            assert result['success'] == True
            assert result['face_count'] == 3
            assert result['total_detected'] == 3
            
            # Check that all faces were processed with appropriate strategies
            for face in result['faces']:
                assert 'crop_metadata' in face
                assert face['crop_metadata']['crop_strategy'] in ['standard', 'small_face', 'large_face']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])