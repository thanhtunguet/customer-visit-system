"""
Enhanced Face Recognition Worker with improved face detection and processing
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import numpy as np
import cv2

from .main import FaceRecognitionWorker, WorkerConfig, FaceDetectedEvent
from .face_processor import FaceProcessor

logger = logging.getLogger(__name__)


class EnhancedFaceRecognitionWorker(FaceRecognitionWorker):
    """
    Enhanced worker with improved face detection and processing capabilities
    """
    
    def __init__(self, config: WorkerConfig):
        super().__init__(config)
        
        # Initialize enhanced face processor
        self.face_processor = FaceProcessor(
            min_face_size=40,
            confidence_threshold=0.6,
            quality_threshold=0.5,
            max_workers=2
        )
        
        # Enhanced processing statistics
        self.processing_stats = {
            'total_frames': 0,
            'faces_detected': 0,
            'high_quality_faces': 0,
            'staff_matches': 0,
            'detection_methods_used': {},
            'average_quality_score': 0.0,
            'processing_issues': []
        }

    async def initialize(self):
        """Initialize worker with enhanced capabilities"""
        await super().initialize()
        logger.info("Enhanced Face Recognition Worker initialized")

    async def shutdown(self):
        """Shutdown with cleanup"""
        await self.face_processor.cleanup()
        await super().shutdown()

    async def process_frame_enhanced(self, frame: np.ndarray) -> Dict[str, Any]:
        """
        Enhanced frame processing with detailed quality assessment and multiple detection methods
        """
        self.processing_stats['total_frames'] += 1
        
        start_time = datetime.now()
        processing_results = {
            'faces_processed': 0,
            'events_sent': 0,
            'processing_time': 0.0,
            'quality_scores': [],
            'detection_methods': [],
            'issues': []
        }
        
        try:
            # Convert frame to bytes for processing
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
            frame_bytes = buffer.tobytes()
            
            # Process with enhanced pipeline
            result = await self.face_processor.process_staff_image(
                frame_bytes, 
                staff_id=f"frame_{self.processing_stats['total_frames']}"
            )
            
            if result['success']:
                self.processing_stats['faces_detected'] += 1
                
                # Extract processing information
                bbox = result['face_bbox']
                landmarks = result.get('face_landmarks')
                confidence = result['confidence']
                embedding = result['embedding']
                quality_score = result['quality_score']
                detector_used = result.get('detector_used', 'unknown')
                processing_notes = result.get('processing_notes', [])
                
                # Update statistics
                self.processing_stats['detection_methods_used'][detector_used] = \
                    self.processing_stats['detection_methods_used'].get(detector_used, 0) + 1
                
                if quality_score >= 0.7:
                    self.processing_stats['high_quality_faces'] += 1
                
                # Check for staff match
                is_staff_local, staff_id = self._is_staff_match(embedding)
                
                if is_staff_local:
                    self.processing_stats['staff_matches'] += 1
                    logger.info(f"Staff member detected: {staff_id} (quality: {quality_score:.2f})")
                
                # Create enhanced face event
                event = FaceDetectedEvent(
                    tenant_id=self.config.tenant_id,
                    site_id=self.config.site_id,
                    camera_id=int(self.config.camera_id) if self.config.camera_id else 1,
                    timestamp=datetime.now(timezone.utc),
                    embedding=embedding,
                    bbox=bbox,
                    is_staff_local=is_staff_local,
                    staff_id=staff_id if is_staff_local else None
                )
                
                # Send event to API
                try:
                    api_result = await self._send_face_event(event)
                    if 'error' not in api_result:
                        processing_results['events_sent'] = 1
                    else:
                        processing_results['issues'].append(f"API error: {api_result['error']}")
                except Exception as e:
                    processing_results['issues'].append(f"Failed to send event: {e}")
                
                # Update processing results
                processing_results['faces_processed'] = 1
                processing_results['quality_scores'].append(quality_score)
                processing_results['detection_methods'].append(detector_used)
                
                # Log processing notes
                if processing_notes:
                    logger.info(f"Processing notes: {', '.join(processing_notes)}")
                
            else:
                # Handle processing failure
                error = result.get('error', 'Unknown error')
                quality_score = result.get('quality_score', 0.0)
                issues = result.get('issues', [])
                suggestions = result.get('suggestions', [])
                
                processing_results['issues'].append(error)
                
                if issues:
                    logger.debug(f"Image quality issues: {', '.join(issues)}")
                
                if suggestions:
                    logger.debug(f"Improvement suggestions: {', '.join(suggestions)}")
                
                # Update statistics for failed processing
                self.processing_stats['processing_issues'].append({
                    'timestamp': datetime.now().isoformat(),
                    'error': error,
                    'quality_score': quality_score,
                    'issues': issues,
                    'suggestions': suggestions
                })
        
        except Exception as e:
            logger.error(f"Enhanced frame processing failed: {e}")
            processing_results['issues'].append(f"Processing exception: {e}")
        
        finally:
            # Calculate processing time
            processing_results['processing_time'] = (datetime.now() - start_time).total_seconds()
            
            # Update average quality score
            if processing_results['quality_scores']:
                current_avg = self.processing_stats['average_quality_score']
                total_faces = self.processing_stats['faces_detected']
                new_scores = processing_results['quality_scores']
                
                if total_faces > 0:
                    # Update running average
                    self.processing_stats['average_quality_score'] = (
                        (current_avg * (total_faces - len(new_scores)) + sum(new_scores)) / total_faces
                    )
                else:
                    self.processing_stats['average_quality_score'] = sum(new_scores) / len(new_scores)
        
        return processing_results

    def get_processing_statistics(self) -> Dict[str, Any]:
        """Get comprehensive processing statistics"""
        stats = self.processing_stats.copy()
        
        # Calculate success rates
        if stats['total_frames'] > 0:
            stats['detection_rate'] = stats['faces_detected'] / stats['total_frames']
            stats['high_quality_rate'] = stats['high_quality_faces'] / stats['total_frames']
        else:
            stats['detection_rate'] = 0.0
            stats['high_quality_rate'] = 0.0
        
        if stats['faces_detected'] > 0:
            stats['staff_match_rate'] = stats['staff_matches'] / stats['faces_detected']
        else:
            stats['staff_match_rate'] = 0.0
        
        # Get most successful detection method
        if stats['detection_methods_used']:
            stats['best_detection_method'] = max(
                stats['detection_methods_used'].items(),
                key=lambda x: x[1]
            )[0]
        else:
            stats['best_detection_method'] = None
        
        return stats

    def get_quality_report(self) -> Dict[str, Any]:
        """Generate quality assessment report"""
        recent_issues = self.processing_stats['processing_issues'][-50:]  # Last 50 issues
        
        # Analyze common issues
        issue_types = {}
        suggestions_freq = {}
        
        for issue in recent_issues:
            # Count issue types
            for issue_text in issue.get('issues', []):
                issue_types[issue_text] = issue_types.get(issue_text, 0) + 1
            
            # Count suggestions
            for suggestion in issue.get('suggestions', []):
                suggestions_freq[suggestion] = suggestions_freq.get(suggestion, 0) + 1
        
        return {
            'total_processing_attempts': self.processing_stats['total_frames'],
            'successful_detections': self.processing_stats['faces_detected'],
            'average_quality_score': self.processing_stats['average_quality_score'],
            'detection_methods_performance': self.processing_stats['detection_methods_used'],
            'common_issues': dict(sorted(issue_types.items(), key=lambda x: x[1], reverse=True)),
            'recommended_improvements': dict(sorted(suggestions_freq.items(), key=lambda x: x[1], reverse=True)),
            'quality_recommendations': self._generate_quality_recommendations()
        }

    def _generate_quality_recommendations(self) -> List[str]:
        """Generate recommendations based on processing statistics"""
        recommendations = []
        
        stats = self.processing_stats
        
        # Detection rate recommendations
        if stats['total_frames'] > 0:
            detection_rate = stats['faces_detected'] / stats['total_frames']
            
            if detection_rate < 0.3:
                recommendations.append("Low face detection rate - consider improving lighting or camera positioning")
            
            # Quality rate recommendations
            if stats['faces_detected'] > 0:
                quality_rate = stats['high_quality_faces'] / stats['faces_detected']
                
                if quality_rate < 0.5:
                    recommendations.append("Many low-quality face detections - improve image resolution or focus")
        
        # Detection method recommendations
        if stats['detection_methods_used']:
            method_counts = stats['detection_methods_used']
            
            if 'haar' in method_counts and method_counts['haar'] > sum(method_counts.values()) * 0.5:
                recommendations.append("Frequently using basic Haar detector - consider installing advanced detection libraries")
            
            if 'retinaface' not in method_counts and 'mtcnn' not in method_counts:
                recommendations.append("Install RetinaFace or MTCNN for better detection of challenging poses")
        
        # Average quality recommendations
        if stats['average_quality_score'] < 0.6:
            recommendations.append("Overall image quality is low - improve camera settings or environmental conditions")
        
        if not recommendations:
            recommendations.append("Face detection performance is good - no major improvements needed")
        
        return recommendations

    async def run_enhanced_camera_capture(self):
        """
        Run camera capture with enhanced processing and monitoring
        """
        logger.info("Starting enhanced camera capture with improved face detection")
        
        cap = None
        consecutive_failures = 0
        max_consecutive_failures = 10
        
        try:
            # Initialize camera
            if self.config.rtsp_url:
                cap = cv2.VideoCapture(self.config.rtsp_url)
                logger.info(f"Connecting to RTSP stream: {self.config.rtsp_url}")
            else:
                cap = cv2.VideoCapture(self.config.usb_camera)
                logger.info(f"Connecting to USB camera: {self.config.usb_camera}")
            
            if not cap.isOpened():
                raise RuntimeError("Failed to open camera")
            
            # Set camera properties for better quality
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            cap.set(cv2.CAP_PROP_FPS, 15)
            
            frame_interval = 1.0 / self.config.worker_fps
            last_process_time = 0
            
            logger.info(f"Enhanced camera capture started (FPS: {self.config.worker_fps})")
            
            while True:
                current_time = asyncio.get_event_loop().time()
                
                if current_time - last_process_time < frame_interval:
                    await asyncio.sleep(0.01)
                    continue
                
                ret, frame = cap.read()
                
                if not ret:
                    consecutive_failures += 1
                    logger.warning(f"Failed to read frame (failure {consecutive_failures})")
                    
                    if consecutive_failures >= max_consecutive_failures:
                        logger.error("Too many consecutive camera failures")
                        break
                    
                    await asyncio.sleep(0.1)
                    continue
                
                # Reset failure counter on successful read
                consecutive_failures = 0
                
                # Process frame with enhanced pipeline
                try:
                    processing_result = await self.process_frame_enhanced(frame)
                    
                    # Log processing summary
                    if processing_result['faces_processed'] > 0:
                        quality_scores = processing_result.get('quality_scores', [])
                        avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0
                        detection_methods = processing_result.get('detection_methods', [])
                        
                        logger.info(
                            f"Frame processed: {processing_result['faces_processed']} faces, "
                            f"avg quality: {avg_quality:.2f}, "
                            f"methods: {', '.join(detection_methods)}, "
                            f"time: {processing_result['processing_time']:.2f}s"
                        )
                    
                    # Log issues if any
                    if processing_result.get('issues'):
                        logger.debug(f"Processing issues: {', '.join(processing_result['issues'])}")
                
                except Exception as e:
                    logger.error(f"Frame processing failed: {e}")
                    consecutive_failures += 1
                
                last_process_time = current_time
                
                # Periodic statistics logging
                if self.processing_stats['total_frames'] % 100 == 0:
                    stats = self.get_processing_statistics()
                    logger.info(
                        f"Processing stats - Frames: {stats['total_frames']}, "
                        f"Detection rate: {stats['detection_rate']:.2%}, "
                        f"Quality rate: {stats['high_quality_rate']:.2%}, "
                        f"Staff matches: {stats['staff_matches']}"
                    )
        
        except Exception as e:
            logger.error(f"Enhanced camera capture failed: {e}")
            raise
        
        finally:
            if cap:
                cap.release()
                logger.info("Camera released")

    async def run_enhanced_simulation(self):
        """
        Run enhanced simulation with various test scenarios
        """
        logger.info("Starting enhanced simulation with test scenarios")
        
        # Test scenarios with different image types
        test_scenarios = [
            "high_quality_frontal",
            "low_light",
            "tilted_head",
            "profile_view", 
            "grayscale",
            "blurry",
            "small_face",
            "multiple_faces"
        ]
        
        for scenario in test_scenarios:
            logger.info(f"Testing scenario: {scenario}")
            
            # Generate test frame based on scenario
            test_frame = self._generate_test_frame(scenario)
            
            try:
                processing_result = await self.process_frame_enhanced(test_frame)
                
                logger.info(
                    f"Scenario '{scenario}' - "
                    f"Faces: {processing_result['faces_processed']}, "
                    f"Quality: {processing_result.get('quality_scores', [0])[0] if processing_result.get('quality_scores') else 0:.2f}"
                )
                
            except Exception as e:
                logger.error(f"Scenario '{scenario}' failed: {e}")
            
            await asyncio.sleep(2)  # Delay between scenarios
        
        # Print final statistics
        stats = self.get_processing_statistics()
        quality_report = self.get_quality_report()
        
        logger.info("=== Enhanced Simulation Complete ===")
        logger.info(f"Total scenarios: {len(test_scenarios)}")
        logger.info(f"Detection rate: {stats['detection_rate']:.2%}")
        logger.info(f"Average quality: {stats['average_quality_score']:.2f}")
        logger.info(f"Detection methods used: {stats['detection_methods_used']}")
        logger.info(f"Recommendations: {quality_report['quality_recommendations']}")

    def _generate_test_frame(self, scenario: str) -> np.ndarray:
        """Generate test frames for different scenarios"""
        # Base frame (640x480, color)
        frame = np.random.randint(50, 200, (480, 640, 3), dtype=np.uint8)
        
        # Add face-like regions based on scenario
        if scenario == "high_quality_frontal":
            # Add a clear, well-lit rectangular region
            cv2.rectangle(frame, (250, 150), (390, 330), (180, 160, 140), -1)
            # Add "eyes"
            cv2.circle(frame, (280, 200), 8, (50, 50, 50), -1)
            cv2.circle(frame, (360, 200), 8, (50, 50, 50), -1)
            
        elif scenario == "low_light":
            # Darken the entire frame
            frame = (frame * 0.3).astype(np.uint8)
            cv2.rectangle(frame, (250, 150), (390, 330), (60, 50, 45), -1)
            
        elif scenario == "grayscale":
            # Convert to grayscale then back to BGR
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            frame = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
            cv2.rectangle(frame, (250, 150), (390, 330), (120, 120, 120), -1)
            
        elif scenario == "blurry":
            # Apply blur
            frame = cv2.GaussianBlur(frame, (15, 15), 0)
            cv2.rectangle(frame, (250, 150), (390, 330), (150, 130, 110), -1)
            
        elif scenario == "small_face":
            # Smaller face region
            cv2.rectangle(frame, (300, 200), (340, 240), (160, 140, 120), -1)
            
        elif scenario == "multiple_faces":
            # Add multiple face-like regions
            regions = [(200, 100, 280, 200), (360, 120, 440, 220), (280, 300, 360, 400)]
            for x1, y1, x2, y2 in regions:
                cv2.rectangle(frame, (x1, y1), (x2, y2), (170, 150, 130), -1)
        
        return frame