"""
Unit tests for enhanced face cropping functionality

Tests various scenarios:
- Very large faces (close to camera)
- Very small faces (far from camera)
- Multiple faces with different selection strategies
- Edge cases (faces near frame boundaries)
- Aspect ratio preservation
- Configuration parameter handling
"""

import pytest
import numpy as np
import cv2
import os
from unittest.mock import patch, MagicMock
import tempfile

from app.face_cropper import FaceCropper, PrimaryFaceStrategy


class TestFaceCropper:
    """Test suite for FaceCropper class"""
    
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
    
    @pytest.fixture
    def normal_face(self):
        """Normal-sized face"""
        return {
            'bbox': [200, 150, 120, 150],  # Medium 120x150 face
            'confidence': 0.85,
            'landmarks': [[240, 180], [280, 180], [260, 220], [240, 260], [280, 260]]
        }
    
    @pytest.fixture
    def edge_face(self):
        """Face near image edge"""
        return {
            'bbox': [600, 400, 80, 100],  # Face near bottom-right edge
            'confidence': 0.75,
            'landmarks': None
        }
    
    def test_initialization_default_values(self):
        """Test FaceCropper initialization with default values"""
        cropper = FaceCropper()
        
        assert cropper.min_face_size == 40
        assert cropper.crop_margin_pct == 0.15
        assert cropper.target_size == 224
        assert cropper.primary_face_strategy == PrimaryFaceStrategy.BEST_QUALITY
        assert cropper.max_face_ratio == 0.6
        assert cropper.preserve_aspect == True
    
    def test_initialization_custom_values(self):
        """Test FaceCropper initialization with custom values"""
        cropper = FaceCropper(
            min_face_size=60,
            crop_margin_pct=0.2,
            target_size=160,
            primary_face_strategy='largest',
            max_face_ratio=0.7,
            preserve_aspect=False
        )
        
        assert cropper.min_face_size == 60
        assert cropper.crop_margin_pct == 0.2
        assert cropper.target_size == 160
        assert cropper.primary_face_strategy == PrimaryFaceStrategy.LARGEST
        assert cropper.max_face_ratio == 0.7
        assert cropper.preserve_aspect == False
    
    @patch.dict(os.environ, {
        'MIN_FACE_SIZE': '50',
        'CROP_MARGIN_PCT': '0.25',
        'TARGET_SIZE': '160',
        'PRIMARY_FACE_STRATEGY': 'most_centered',
        'MAX_FACE_RATIO': '0.5',
        'PRESERVE_ASPECT': 'false'
    })
    def test_initialization_from_env(self):
        """Test FaceCropper initialization from environment variables"""
        cropper = FaceCropper()
        
        assert cropper.min_face_size == 50
        assert cropper.crop_margin_pct == 0.25
        assert cropper.target_size == 160
        assert cropper.primary_face_strategy == PrimaryFaceStrategy.MOST_CENTERED
        assert cropper.max_face_ratio == 0.5
        assert cropper.preserve_aspect == False
    
    def test_crop_large_face(self, sample_image, large_face):
        """Test cropping a very large face"""
        cropper = FaceCropper()
        result = cropper.crop_face(sample_image, large_face, debug=True)
        
        assert result['crop_strategy'] == 'large_face'
        assert result['face_ratio'] > cropper.max_face_ratio
        assert 'cropped_face' in result
        assert result['cropped_face'].shape == (cropper.target_size, cropper.target_size, 3)
        
        # Check that conservative margin was applied
        debug_info = result['debug_info']
        assert debug_info['applied_margin_pct'] <= 0.05
    
    def test_crop_small_face(self, sample_image, small_face):
        """Test cropping a very small face"""
        cropper = FaceCropper()
        result = cropper.crop_face(sample_image, small_face, debug=True)
        
        assert result['crop_strategy'] == 'small_face'
        assert 'cropped_face' in result
        assert result['cropped_face'].shape == (cropper.target_size, cropper.target_size, 3)
        
        # Check that expanded margin was applied
        debug_info = result['debug_info']
        assert debug_info['applied_margin_pct'] >= 0.25
    
    def test_crop_normal_face(self, sample_image, normal_face):
        """Test cropping a normal-sized face"""
        cropper = FaceCropper()
        result = cropper.crop_face(sample_image, normal_face, debug=True)
        
        assert result['crop_strategy'] == 'standard'
        assert 'cropped_face' in result
        assert result['cropped_face'].shape == (cropper.target_size, cropper.target_size, 3)
        
        # Check that normal margin was applied
        debug_info = result['debug_info']
        assert debug_info['margin_pct'] == cropper.crop_margin_pct
    
    def test_crop_edge_face(self, sample_image, edge_face):
        """Test cropping a face near image edge"""
        cropper = FaceCropper()
        result = cropper.crop_face(sample_image, edge_face)
        
        # Should handle edge case without crashing
        assert 'cropped_face' in result
        assert result['cropped_face'].shape == (cropper.target_size, cropper.target_size, 3)
        
        # Validate the crop is within image bounds
        crop_bbox = result['crop_bbox']
        assert crop_bbox[0] >= 0  # x >= 0
        assert crop_bbox[1] >= 0  # y >= 0
        assert crop_bbox[0] + crop_bbox[2] <= sample_image.shape[1]  # x + w <= img_width
        assert crop_bbox[1] + crop_bbox[3] <= sample_image.shape[0]  # y + h <= img_height
    
    def test_multiple_faces_largest_strategy(self, sample_image):
        """Test multiple face handling with LARGEST strategy"""
        faces = [
            {'bbox': [100, 100, 80, 100], 'confidence': 0.8},   # Medium face
            {'bbox': [300, 200, 120, 150], 'confidence': 0.7},  # Large face
            {'bbox': [500, 300, 60, 80], 'confidence': 0.9}     # Small face
        ]
        
        cropper = FaceCropper(primary_face_strategy='largest')
        result = cropper.crop_multiple_faces(sample_image, faces)
        
        assert result['selected_face_index'] == 1  # Should select the largest face
        assert result['selection_strategy'] == 'largest'
        assert result['total_faces'] == 3
    
    def test_multiple_faces_highest_confidence_strategy(self, sample_image):
        """Test multiple face handling with HIGHEST_CONFIDENCE strategy"""
        faces = [
            {'bbox': [100, 100, 80, 100], 'confidence': 0.8},   # Medium confidence
            {'bbox': [300, 200, 120, 150], 'confidence': 0.7},  # Low confidence
            {'bbox': [500, 300, 60, 80], 'confidence': 0.9}     # High confidence
        ]
        
        cropper = FaceCropper(primary_face_strategy='highest_confidence')
        result = cropper.crop_multiple_faces(sample_image, faces)
        
        assert result['selected_face_index'] == 2  # Should select highest confidence
        assert result['selection_strategy'] == 'highest_confidence'
    
    def test_multiple_faces_most_centered_strategy(self, sample_image):
        """Test multiple face handling with MOST_CENTERED strategy"""
        # Image center is at (320, 240) for 640x480 image
        faces = [
            {'bbox': [50, 50, 60, 80], 'confidence': 0.8},      # Top-left
            {'bbox': [290, 210, 60, 80], 'confidence': 0.7},    # Near center (center at 320,250)
            {'bbox': [500, 400, 60, 80], 'confidence': 0.9}     # Bottom-right
        ]
        
        cropper = FaceCropper(primary_face_strategy='most_centered')
        result = cropper.crop_multiple_faces(sample_image, faces)
        
        assert result['selected_face_index'] == 1  # Should select the most centered face
        assert result['selection_strategy'] == 'most_centered'
    
    def test_multiple_faces_best_quality_strategy(self, sample_image):
        """Test multiple face handling with BEST_QUALITY strategy"""
        faces = [
            {'bbox': [100, 100, 50, 60], 'confidence': 0.6, 'landmarks': None},
            {'bbox': [300, 200, 80, 100], 'confidence': 0.8, 'landmarks': [[320, 220], [360, 220], [340, 250], [320, 280], [360, 280]]},
            {'bbox': [500, 300, 40, 50], 'confidence': 0.9, 'landmarks': None}
        ]
        
        cropper = FaceCropper(primary_face_strategy='best_quality')
        result = cropper.crop_multiple_faces(sample_image, faces)
        
        # Should likely select face with landmarks and good confidence
        assert result['selection_strategy'] == 'best_quality'
        assert 'selected_face_index' in result
    
    def test_aspect_ratio_preservation(self, sample_image):
        """Test aspect ratio preservation with letterboxing"""
        # Create a rectangular face crop to test aspect preservation
        face = {'bbox': [200, 100, 100, 200], 'confidence': 0.8}  # Tall rectangle
        
        cropper = FaceCropper(preserve_aspect=True, target_size=224)
        result = cropper.crop_face(sample_image, face)
        
        assert result['cropped_face'].shape == (224, 224, 3)
        
        # Test without aspect preservation
        cropper_no_aspect = FaceCropper(preserve_aspect=False, target_size=224)
        result_no_aspect = cropper_no_aspect.crop_face(sample_image, face)
        
        assert result_no_aspect['cropped_face'].shape == (224, 224, 3)
    
    def test_validate_crop_result(self):
        """Test crop result validation"""
        cropper = FaceCropper()
        
        # Valid crop result
        valid_result = {
            'cropped_face': np.ones((100, 100, 3), dtype=np.uint8)
        }
        assert cropper.validate_crop_result(valid_result) == True
        
        # Invalid crop results
        assert cropper.validate_crop_result({}) == False
        assert cropper.validate_crop_result({'cropped_face': None}) == False
        assert cropper.validate_crop_result({'cropped_face': np.array([])}) == False
        
        # Too small crop
        tiny_crop = {'cropped_face': np.ones((10, 10, 3), dtype=np.uint8)}
        assert cropper.validate_crop_result(tiny_crop) == False
    
    def test_get_config_info(self):
        """Test getting configuration information"""
        cropper = FaceCropper(
            min_face_size=50,
            crop_margin_pct=0.2,
            target_size=160,
            primary_face_strategy='largest'
        )
        
        config = cropper.get_config_info()
        
        expected_config = {
            'min_face_size': 50,
            'crop_margin_pct': 0.2,
            'target_size': 160,
            'primary_face_strategy': 'largest',
            'max_face_ratio': 0.6,
            'preserve_aspect': True
        }
        
        assert config == expected_config
    
    def test_empty_face_list(self, sample_image):
        """Test handling of empty face list"""
        cropper = FaceCropper()
        
        with pytest.raises(ValueError, match="No faces provided for cropping"):
            cropper.crop_multiple_faces(sample_image, [])
    
    def test_single_face_in_multiple_faces(self, sample_image, normal_face):
        """Test handling single face in multiple faces method"""
        cropper = FaceCropper()
        result = cropper.crop_multiple_faces(sample_image, [normal_face])
        
        assert 'total_faces' in result
        assert result['total_faces'] == 1
        assert 'cropped_face' in result
    
    def test_zero_sized_crop_fallback(self):
        """Test handling of zero-sized crops"""
        cropper = FaceCropper()
        
        # Test _resize_to_target with empty image
        result = cropper._resize_to_target(np.array([]), debug=False)
        
        assert result.shape == (cropper.target_size, cropper.target_size, 3)
        assert np.all(result == 0)  # Should be black image
    
    def test_invalid_strategy_fallback(self):
        """Test handling of invalid primary face strategy"""
        with patch('app.face_cropper.logger') as mock_logger:
            cropper = FaceCropper(primary_face_strategy='invalid_strategy')
            
            # Should fallback to BEST_QUALITY
            assert cropper.primary_face_strategy == PrimaryFaceStrategy.BEST_QUALITY
            mock_logger.warning.assert_called_once()


class TestFaceCropperIntegration:
    """Integration tests for face cropper with realistic scenarios"""
    
    def create_synthetic_face_image(self, face_size_ratio: float, position: str = 'center') -> Tuple[np.ndarray, Dict]:
        """
        Create synthetic image with face for testing
        
        Args:
            face_size_ratio: Ratio of face size to image size (0.1 = 10% of image)
            position: 'center', 'edge', 'corner'
        
        Returns:
            Tuple of (image, face_info)
        """
        img_h, img_w = 480, 640
        image = np.random.randint(50, 200, (img_h, img_w, 3), dtype=np.uint8)
        
        # Calculate face size
        face_size = int(min(img_h, img_w) * face_size_ratio)
        face_w = face_h = face_size
        
        # Position face based on parameter
        if position == 'center':
            x = (img_w - face_w) // 2
            y = (img_h - face_h) // 2
        elif position == 'edge':
            x = img_w - face_w - 10  # Near right edge
            y = (img_h - face_h) // 2
        elif position == 'corner':
            x = 10  # Near left edge
            y = 10  # Near top edge
        else:
            x = y = 50  # Default
        
        # Draw a simple face-like pattern
        cv2.rectangle(image, (x, y), (x + face_w, y + face_h), (150, 150, 150), -1)
        cv2.circle(image, (x + face_w//3, y + face_h//3), face_w//10, (50, 50, 50), -1)  # Left eye
        cv2.circle(image, (x + 2*face_w//3, y + face_h//3), face_w//10, (50, 50, 50), -1)  # Right eye
        cv2.ellipse(image, (x + face_w//2, y + 2*face_h//3), (face_w//6, face_h//8), 0, 0, 180, (100, 100, 100), -1)  # Mouth
        
        face_info = {
            'bbox': [x, y, face_w, face_h],
            'confidence': 0.8,
            'landmarks': [
                [x + face_w//3, y + face_h//3],      # Left eye
                [x + 2*face_w//3, y + face_h//3],    # Right eye
                [x + face_w//2, y + face_h//2],      # Nose
                [x + face_w//3, y + 2*face_h//3],    # Left mouth
                [x + 2*face_w//3, y + 2*face_h//3]   # Right mouth
            ]
        }
        
        return image, face_info
    
    def test_huge_face_scenario(self):
        """Test face that occupies most of frame (webcam very close)"""
        image, face_info = self.create_synthetic_face_image(0.8, 'center')  # 80% of image
        
        cropper = FaceCropper()
        result = cropper.crop_face(image, face_info, debug=True)
        
        assert result['crop_strategy'] == 'large_face'
        assert result['face_ratio'] > 0.6  # Much larger than max_face_ratio
        assert cropper.validate_crop_result(result)
        
        # Should use conservative margin
        debug_info = result['debug_info']
        assert debug_info['applied_margin_pct'] <= 0.05
    
    def test_tiny_face_scenario(self):
        """Test face that is very small in frame (webcam far away)"""
        image, face_info = self.create_synthetic_face_image(0.05, 'center')  # 5% of image
        
        cropper = FaceCropper()
        result = cropper.crop_face(image, face_info, debug=True)
        
        assert result['crop_strategy'] == 'small_face'
        assert result['face_ratio'] < 0.1  # Very small
        assert cropper.validate_crop_result(result)
        
        # Should use expanded margin
        debug_info = result['debug_info']
        assert debug_info['applied_margin_pct'] >= 0.25
    
    def test_edge_case_scenarios(self):
        """Test faces near edges and corners"""
        scenarios = [
            ('edge', 0.15),
            ('corner', 0.12)
        ]
        
        cropper = FaceCropper()
        
        for position, face_ratio in scenarios:
            image, face_info = self.create_synthetic_face_image(face_ratio, position)
            result = cropper.crop_face(image, face_info)
            
            assert cropper.validate_crop_result(result)
            
            # Verify crop is within image bounds
            crop_bbox = result['crop_bbox']
            assert crop_bbox[0] >= 0
            assert crop_bbox[1] >= 0
            assert crop_bbox[0] + crop_bbox[2] <= image.shape[1]
            assert crop_bbox[1] + crop_bbox[3] <= image.shape[0]
    
    def test_multiple_face_scenarios(self):
        """Test realistic multi-face scenarios"""
        img_h, img_w = 480, 640
        image = np.random.randint(50, 200, (img_h, img_w, 3), dtype=np.uint8)
        
        # Create multiple faces of different sizes
        faces = []
        
        # Large face (person close to camera)
        large_face = {
            'bbox': [50, 50, 200, 250],
            'confidence': 0.9,
            'landmarks': [[120, 120], [180, 120], [150, 170], [120, 220], [180, 220]]
        }
        faces.append(large_face)
        
        # Medium face (person at normal distance)  
        medium_face = {
            'bbox': [300, 150, 100, 120],
            'confidence': 0.85,
            'landmarks': [[330, 180], [370, 180], [350, 210], [330, 240], [370, 240]]
        }
        faces.append(medium_face)
        
        # Small face (person far away)
        small_face = {
            'bbox': [500, 300, 60, 70],
            'confidence': 0.7,
            'landmarks': None
        }
        faces.append(small_face)
        
        # Test different strategies
        strategies = ['largest', 'highest_confidence', 'most_centered', 'best_quality']
        
        for strategy in strategies:
            cropper = FaceCropper(primary_face_strategy=strategy)
            result = cropper.crop_multiple_faces(image, faces)
            
            assert cropper.validate_crop_result(result)
            assert result['selection_strategy'] == strategy
            assert result['total_faces'] == 3
            assert 0 <= result['selected_face_index'] < 3
    
    def test_target_size_variations(self):
        """Test different target sizes"""
        image, face_info = self.create_synthetic_face_image(0.2, 'center')
        
        target_sizes = [112, 160, 224, 256]
        
        for target_size in target_sizes:
            cropper = FaceCropper(target_size=target_size)
            result = cropper.crop_face(image, face_info)
            
            assert result['cropped_face'].shape == (target_size, target_size, 3)
            assert cropper.validate_crop_result(result)
    
    def test_margin_variations(self):
        """Test different margin percentages"""
        image, face_info = self.create_synthetic_face_image(0.15, 'center')
        
        margin_percentages = [0.05, 0.1, 0.15, 0.2, 0.3]
        
        for margin_pct in margin_percentages:
            cropper = FaceCropper(crop_margin_pct=margin_pct)
            result = cropper.crop_face(image, face_info, debug=True)
            
            assert cropper.validate_crop_result(result)
            
            if result['crop_strategy'] == 'standard':
                debug_info = result['debug_info']
                assert abs(debug_info['margin_pct'] - margin_pct) < 0.01


if __name__ == '__main__':
    pytest.main([__file__, '-v'])