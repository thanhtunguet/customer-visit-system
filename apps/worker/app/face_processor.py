"""
Enhanced face processing service for staff face matching
Integrates improved detection, preprocessing, and embedding generation
"""

import cv2
import numpy as np
import logging
from typing import List, Dict, Optional, Tuple, Any
from pathlib import Path
import asyncio
from concurrent.futures import ThreadPoolExecutor

from .improved_detectors import ImprovedFaceDetector, ImprovedFaceEmbedder

logger = logging.getLogger(__name__)


class FaceProcessor:
    """
    Enhanced face processor that handles the complete pipeline:
    1. Image preprocessing and quality assessment
    2. Multi-detector face detection with fallbacks
    3. Face quality scoring and filtering
    4. Advanced face alignment and preprocessing
    5. Robust embedding generation
    """
    
    def __init__(self, 
                 min_face_size: int = 40,
                 confidence_threshold: float = 0.6,
                 quality_threshold: float = 0.5,
                 max_workers: int = 2):
        
        self.min_face_size = min_face_size
        self.confidence_threshold = confidence_threshold
        self.quality_threshold = quality_threshold
        
        # Initialize enhanced detectors
        self.detector = ImprovedFaceDetector(
            use_mtcnn=True,
            use_retinaface=True,
            min_face_size=min_face_size,
            confidence_threshold=confidence_threshold
        )
        
        self.embedder = ImprovedFaceEmbedder()
        
        # Thread pool for CPU-intensive operations
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

    async def process_staff_image(self, image_data: bytes, staff_id: str) -> Dict[str, Any]:
        """
        Process a staff member's face image with enhanced pipeline
        Returns processing results including quality metrics and embeddings
        """
        try:
            # Decode image
            image = await self._decode_image(image_data)
            if image is None:
                return {
                    'success': False,
                    'error': 'Failed to decode image',
                    'quality_score': 0.0
                }
            
            # Assess initial image quality
            quality_assessment = await self._assess_image_quality(image)
            
            # Enhanced face detection
            faces = await self._detect_faces_enhanced(image)
            
            if not faces:
                return {
                    'success': False,
                    'error': 'No faces detected',
                    'quality_score': quality_assessment['overall_quality'],
                    'issues': quality_assessment['issues'],
                    'suggestions': self._get_quality_suggestions(quality_assessment)
                }
            
            # Select the best face
            best_face = await self._select_best_face(faces, image)
            
            # Generate embedding
            embedding = await self._generate_embedding(image, best_face)
            
            # Calculate final quality score
            final_quality = await self._calculate_final_quality(
                best_face, quality_assessment, embedding
            )
            
            return {
                'success': True,
                'face_bbox': best_face['bbox'],
                'face_landmarks': best_face.get('landmarks'),
                'confidence': best_face['confidence'],
                'embedding': embedding,
                'quality_score': final_quality,
                'detector_used': best_face.get('detector'),
                'processing_notes': self._get_processing_notes(best_face, quality_assessment)
            }
            
        except Exception as e:
            logger.error(f"Staff image processing failed for {staff_id}: {e}")
            return {
                'success': False,
                'error': f'Processing failed: {str(e)}',
                'quality_score': 0.0
            }

    async def batch_process_staff_images(self, images_data: List[Tuple[bytes, str]]) -> List[Dict[str, Any]]:
        """
        Process multiple staff images in parallel with optimized resource usage
        """
        results = []
        
        # Process in small batches to manage memory
        batch_size = 3
        for i in range(0, len(images_data), batch_size):
            batch = images_data[i:i + batch_size]
            
            # Process batch concurrently
            batch_tasks = [
                self.process_staff_image(image_data, staff_id)
                for image_data, staff_id in batch
            ]
            
            batch_results = await asyncio.gather(*batch_tasks)
            results.extend(batch_results)
            
            # Small delay between batches to prevent resource exhaustion
            if i + batch_size < len(images_data):
                await asyncio.sleep(0.1)
        
        return results

    async def _decode_image(self, image_data: bytes) -> Optional[np.ndarray]:
        """Decode image data with error handling"""
        try:
            # Convert bytes to numpy array
            nparr = np.frombuffer(image_data, np.uint8)
            
            # Decode image
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if image is None:
                logger.warning("Failed to decode image data")
                return None
            
            return image
            
        except Exception as e:
            logger.error(f"Image decoding failed: {e}")
            return None

    async def _assess_image_quality(self, image: np.ndarray) -> Dict[str, Any]:
        """
        Comprehensive image quality assessment
        """
        def assess_quality():
            height, width = image.shape[:2]
            
            # Convert to grayscale for analysis
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
            
            issues = []
            quality_scores = []
            
            # 1. Resolution check
            min_resolution = 120
            resolution_score = min(1.0, min(height, width) / min_resolution)
            quality_scores.append(resolution_score)
            
            if min(height, width) < min_resolution:
                issues.append(f"Low resolution ({width}x{height}, recommended: ≥{min_resolution}x{min_resolution})")
            
            # 2. Brightness analysis
            brightness = gray.mean()
            brightness_score = 1.0 - abs(brightness - 128) / 128  # Optimal around 128
            quality_scores.append(brightness_score * 0.8)  # Weight less than other factors
            
            if brightness < 50:
                issues.append("Image too dark")
            elif brightness > 200:
                issues.append("Image too bright")
            
            # 3. Contrast analysis
            contrast = gray.std()
            contrast_score = min(1.0, contrast / 50)  # Good contrast > 50
            quality_scores.append(contrast_score)
            
            if contrast < 20:
                issues.append("Low contrast")
            
            # 4. Sharpness analysis (Laplacian variance)
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            sharpness_score = min(1.0, laplacian_var / 500)  # Good sharpness > 500
            quality_scores.append(sharpness_score)
            
            if laplacian_var < 100:
                issues.append("Image appears blurry")
            
            # 5. Noise analysis
            noise_level = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21).std()
            original_std = gray.std()
            noise_ratio = 1 - (noise_level / original_std) if original_std > 0 else 0.5
            noise_score = max(0.3, noise_ratio)  # Minimum score for noise
            quality_scores.append(noise_score * 0.7)  # Weight less
            
            if noise_ratio < 0.7:
                issues.append("High noise level")
            
            # 6. Color analysis (if color image)
            color_score = 1.0
            if len(image.shape) == 3:
                # Check if image is essentially grayscale
                b, g, r = cv2.split(image)
                color_variance = np.var([b.mean(), g.mean(), r.mean()])
                
                if color_variance < 10:  # Very low color variance
                    color_score = 0.8
                    issues.append("Image appears to be grayscale or low color")
                else:
                    color_score = 1.0
            
            quality_scores.append(color_score * 0.6)  # Weight less for color
            
            overall_quality = np.mean(quality_scores)
            
            return {
                'overall_quality': overall_quality,
                'resolution_score': resolution_score,
                'brightness_score': brightness_score,
                'contrast_score': contrast_score,
                'sharpness_score': sharpness_score,
                'noise_score': noise_score,
                'color_score': color_score,
                'issues': issues,
                'brightness': brightness,
                'contrast': contrast,
                'sharpness': laplacian_var,
                'dimensions': (width, height)
            }
        
        # Run in thread pool for CPU-intensive operations
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, assess_quality)

    async def _detect_faces_enhanced(self, image: np.ndarray) -> List[Dict]:
        """Enhanced face detection with quality filtering"""
        
        def detect():
            faces = self.detector.detect(image)
            
            # Filter faces by size and quality
            filtered_faces = []
            for face in faces:
                bbox = face['bbox']
                face_width, face_height = bbox[2], bbox[3]
                
                # Size check
                if min(face_width, face_height) < self.min_face_size:
                    continue
                
                # Confidence check
                if face.get('confidence', 0) < self.confidence_threshold:
                    continue
                
                # Add face area for later selection
                face['area'] = face_width * face_height
                
                # Add face quality assessment
                try:
                    x, y, w, h = bbox
                    face_crop = image[y:y+h, x:x+w]
                    face_quality = self._assess_face_crop_quality(face_crop)
                    face['face_quality'] = face_quality
                except:
                    face['face_quality'] = 0.5  # Default quality
                
                filtered_faces.append(face)
            
            return filtered_faces
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, detect)

    def _assess_face_crop_quality(self, face_crop: np.ndarray) -> float:
        """Assess quality of a face crop"""
        if face_crop.size == 0:
            return 0.0
        
        try:
            # Convert to grayscale for analysis
            gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY) if len(face_crop.shape) == 3 else face_crop
            
            # Multiple quality factors
            quality_factors = []
            
            # Sharpness
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            sharpness_score = min(1.0, laplacian_var / 200)
            quality_factors.append(sharpness_score)
            
            # Contrast
            contrast = gray.std()
            contrast_score = min(1.0, contrast / 40)
            quality_factors.append(contrast_score)
            
            # Brightness (face should be well lit)
            brightness = gray.mean()
            brightness_score = 1.0 - abs(brightness - 120) / 120
            quality_factors.append(brightness_score * 0.8)
            
            # Face size quality (larger is generally better for recognition)
            size_score = min(1.0, min(face_crop.shape[:2]) / 100)
            quality_factors.append(size_score)
            
            return np.mean(quality_factors)
            
        except Exception as e:
            logger.debug(f"Face crop quality assessment failed: {e}")
            return 0.5

    async def _select_best_face(self, faces: List[Dict], image: np.ndarray) -> Dict:
        """Select the best face from detected faces using multiple criteria"""
        
        if len(faces) == 1:
            return faces[0]
        
        def calculate_face_score(face):
            score = 0.0
            
            # Confidence score (30% weight)
            confidence = face.get('confidence', 0)
            score += confidence * 0.3
            
            # Has landmarks bonus (25% weight)
            has_landmarks = face.get('landmarks') is not None
            score += (0.25 if has_landmarks else 0)
            
            # Face size (20% weight) - prefer larger faces but not too large
            area = face.get('area', 0)
            image_area = image.shape[0] * image.shape[1]
            size_ratio = area / image_area
            
            # Optimal size ratio is between 0.05 and 0.4
            if 0.05 <= size_ratio <= 0.4:
                size_score = 1.0
            elif size_ratio > 0.4:
                size_score = max(0.5, 1.0 - (size_ratio - 0.4) / 0.6)
            else:
                size_score = size_ratio / 0.05
            
            score += size_score * 0.2
            
            # Face quality (15% weight)
            face_quality = face.get('face_quality', 0.5)
            score += face_quality * 0.15
            
            # Detector quality bonus (10% weight)
            detector = face.get('detector', '')
            detector_bonus = {
                'retinaface': 0.1,
                'mtcnn': 0.08,
                'mediapipe': 0.06,
                'opencv_dnn': 0.04,
                'haar': 0.02
            }.get(detector, 0)
            score += detector_bonus
            
            return score
        
        # Calculate scores for all faces
        scored_faces = [(face, calculate_face_score(face)) for face in faces]
        
        # Sort by score and return the best one
        scored_faces.sort(key=lambda x: x[1], reverse=True)
        
        best_face = scored_faces[0][0]
        logger.debug(f"Selected best face with score {scored_faces[0][1]:.3f} using {best_face.get('detector', 'unknown')} detector")
        
        return best_face

    async def _generate_embedding(self, image: np.ndarray, face_info: Dict) -> List[float]:
        """Generate face embedding with enhanced cropping"""
        
        def generate():
            from .face_cropper import FaceCropper
            
            # Initialize enhanced cropper
            cropper = FaceCropper()
            
            # Crop face using enhanced algorithm
            crop_result = cropper.crop_face(image, face_info, debug=False)
            
            if not cropper.validate_crop_result(crop_result):
                logger.warning("Face cropping failed, falling back to simple crop")
                # Fallback to original simple cropping
                bbox = face_info['bbox']
                x, y, w, h = bbox
                padding = int(min(w, h) * 0.1)
                x_padded = max(0, x - padding)
                y_padded = max(0, y - padding)
                w_padded = min(image.shape[1] - x_padded, w + 2 * padding)
                h_padded = min(image.shape[0] - y_padded, h + 2 * padding)
                face_crop = image[y_padded:y_padded + h_padded, x_padded:x_padded + w_padded]
            else:
                face_crop = crop_result['cropped_face']
            
            # Get landmarks (adjust for crop coordinates if available)
            landmarks = face_info.get('landmarks')
            if landmarks and 'crop_bbox' in crop_result:
                landmarks = np.array(landmarks)
                crop_bbox = crop_result['crop_bbox']
                # Adjust landmark coordinates for the cropped region
                landmarks[:, 0] -= crop_bbox[0]
                landmarks[:, 1] -= crop_bbox[1]
            
            # Generate embedding
            embedding = self.embedder.embed(face_crop, landmarks)
            
            return embedding
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, generate)

    async def _calculate_final_quality(self, face_info: Dict, image_quality: Dict, embedding: List[float]) -> float:
        """Calculate final quality score combining all factors"""
        
        # Base scores
        face_confidence = face_info.get('confidence', 0)
        image_overall_quality = image_quality['overall_quality']
        face_crop_quality = face_info.get('face_quality', 0.5)
        
        # Landmark bonus
        has_landmarks = 1.0 if face_info.get('landmarks') else 0.7
        
        # Detector quality
        detector_quality = {
            'retinaface': 1.0,
            'mtcnn': 0.9,
            'mediapipe': 0.85,
            'opencv_dnn': 0.8,
            'haar': 0.6
        }.get(face_info.get('detector', ''), 0.7)
        
        # Embedding quality (heuristic based on embedding properties)
        embedding_array = np.array(embedding)
        embedding_norm = np.linalg.norm(embedding_array)
        embedding_quality = min(1.0, embedding_norm) if embedding_norm > 0 else 0.5
        
        # Combine all factors with weights
        final_quality = (
            face_confidence * 0.25 +
            image_overall_quality * 0.25 +
            face_crop_quality * 0.20 +
            has_landmarks * 0.15 +
            detector_quality * 0.10 +
            embedding_quality * 0.05
        )
        
        return final_quality

    def _get_processing_notes(self, face_info: Dict, image_quality: Dict) -> List[str]:
        """Generate helpful processing notes"""
        notes = []
        
        detector = face_info.get('detector', 'unknown')
        preprocessing = face_info.get('preprocessing', 'original')
        
        if detector != 'original':
            notes.append(f"Used {detector} detector on {preprocessing} image")
        
        if face_info.get('landmarks'):
            notes.append("Facial landmarks detected for precise alignment")
        else:
            notes.append("No landmarks detected, used basic alignment")
        
        confidence = face_info.get('confidence', 0)
        if confidence < 0.7:
            notes.append(f"Lower detection confidence ({confidence:.2f})")
        
        if image_quality['overall_quality'] < 0.6:
            notes.append("Image quality could be improved")
        
        return notes

    def _get_quality_suggestions(self, quality_assessment: Dict) -> List[str]:
        """Generate suggestions for improving image quality"""
        suggestions = []
        
        if quality_assessment['brightness'] < 50:
            suggestions.append("Increase lighting or brightness")
        elif quality_assessment['brightness'] > 200:
            suggestions.append("Reduce lighting or exposure")
        
        if quality_assessment['contrast'] < 20:
            suggestions.append("Improve image contrast")
        
        if quality_assessment['sharpness'] < 100:
            suggestions.append("Ensure image is in focus and sharp")
        
        if min(quality_assessment['dimensions']) < 200:
            suggestions.append("Use higher resolution image (recommended: 400x400 or larger)")
        
        if quality_assessment.get('noise_score', 1.0) < 0.7:
            suggestions.append("Reduce image noise (use better camera or lighting)")
        
        if not suggestions:
            suggestions.append("Image quality is acceptable")
        
        return suggestions

    async def cleanup(self):
        """Cleanup resources"""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=True)