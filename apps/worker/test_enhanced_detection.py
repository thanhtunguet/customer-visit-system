#!/usr/bin/env python3
"""
Test script for enhanced face detection capabilities
Tests various scenarios and image types to validate improvements
"""

import asyncio
import cv2
import numpy as np
import os
import sys
from pathlib import Path
import logging
import json
from datetime import datetime

# Add app directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.face_processor import FaceProcessor

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EnhancedFaceDetectionTester:
    """Test suite for enhanced face detection"""
    
    def __init__(self):
        self.face_processor = FaceProcessor(
            min_face_size=30,
            confidence_threshold=0.5,
            quality_threshold=0.4,
            max_workers=1
        )
        
        self.test_results = []

    async def create_test_images(self) -> dict:
        """Create various test image scenarios"""
        test_images = {}
        
        # 1. High quality frontal face
        img = np.ones((400, 400, 3), dtype=np.uint8) * 128
        cv2.ellipse(img, (200, 200), (80, 100), 0, 0, 360, (180, 160, 140), -1)
        # Eyes
        cv2.circle(img, (175, 170), 8, (50, 50, 50), -1)
        cv2.circle(img, (225, 170), 8, (50, 50, 50), -1)
        # Nose
        cv2.circle(img, (200, 200), 4, (120, 100, 90), -1)
        # Mouth
        cv2.ellipse(img, (200, 230), (15, 8), 0, 0, 180, (100, 80, 80), -1)
        
        _, buffer = cv2.imencode('.jpg', img)
        test_images['high_quality_frontal'] = buffer.tobytes()
        
        # 2. Low light (dark) image
        dark_img = (img * 0.3).astype(np.uint8)
        _, buffer = cv2.imencode('.jpg', dark_img)
        test_images['low_light'] = buffer.tobytes()
        
        # 3. High contrast (bright) image
        bright_img = np.clip(img * 1.8, 0, 255).astype(np.uint8)
        _, buffer = cv2.imencode('.jpg', bright_img)
        test_images['high_contrast'] = buffer.tobytes()
        
        # 4. Grayscale image
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray_bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY_BGR)
        _, buffer = cv2.imencode('.jpg', gray_bgr)
        test_images['grayscale'] = buffer.tobytes()
        
        # 5. Blurry image
        blurry = cv2.GaussianBlur(img, (11, 11), 0)
        _, buffer = cv2.imencode('.jpg', blurry)
        test_images['blurry'] = buffer.tobytes()
        
        # 6. Noisy image
        noise = np.random.randint(-30, 30, img.shape, dtype=np.int16)
        noisy = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        _, buffer = cv2.imencode('.jpg', noisy)
        test_images['noisy'] = buffer.tobytes()
        
        # 7. Small face (low resolution)
        small_img = cv2.resize(img, (100, 100))
        small_img = cv2.resize(small_img, (400, 400))  # Upscale back
        _, buffer = cv2.imencode('.jpg', small_img)
        test_images['small_face'] = buffer.tobytes()
        
        # 8. Tilted face
        rows, cols = img.shape[:2]
        M = cv2.getRotationMatrix2D((cols/2, rows/2), 25, 1)
        tilted = cv2.warpAffine(img, M, (cols, rows))
        _, buffer = cv2.imencode('.jpg', tilted)
        test_images['tilted_face'] = buffer.tobytes()
        
        # 9. Profile view (simulated)
        profile = np.ones((400, 400, 3), dtype=np.uint8) * 128
        # Draw profile-like shape
        cv2.ellipse(profile, (200, 200), (60, 90), 15, 0, 180, (180, 160, 140), -1)
        cv2.circle(profile, (215, 170), 6, (50, 50, 50), -1)  # Eye
        cv2.circle(profile, (190, 200), 3, (120, 100, 90), -1)  # Nose
        _, buffer = cv2.imencode('.jpg', profile)
        test_images['profile_view'] = buffer.tobytes()
        
        # 10. Multiple faces
        multi_img = np.ones((400, 600, 3), dtype=np.uint8) * 128
        # Face 1
        cv2.ellipse(multi_img, (150, 200), (60, 80), 0, 0, 360, (180, 160, 140), -1)
        cv2.circle(multi_img, (130, 170), 6, (50, 50, 50), -1)
        cv2.circle(multi_img, (170, 170), 6, (50, 50, 50), -1)
        # Face 2
        cv2.ellipse(multi_img, (450, 200), (60, 80), 0, 0, 360, (170, 150, 130), -1)
        cv2.circle(multi_img, (430, 170), 6, (50, 50, 50), -1)
        cv2.circle(multi_img, (470, 170), 6, (50, 50, 50), -1)
        _, buffer = cv2.imencode('.jpg', multi_img)
        test_images['multiple_faces'] = buffer.tobytes()
        
        return test_images

    async def test_scenario(self, scenario_name: str, image_data: bytes) -> dict:
        """Test a specific scenario"""
        logger.info(f"Testing scenario: {scenario_name}")
        
        start_time = datetime.now()
        
        try:
            result = await self.face_processor.process_staff_image(
                image_data, 
                staff_id=f"test_{scenario_name}"
            )
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            test_result = {
                'scenario': scenario_name,
                'success': result['success'],
                'processing_time': processing_time,
                'timestamp': start_time.isoformat()
            }
            
            if result['success']:
                test_result.update({
                    'confidence': result['confidence'],
                    'quality_score': result['quality_score'],
                    'has_landmarks': result.get('face_landmarks') is not None,
                    'detector_used': result.get('detector_used'),
                    'face_bbox': result.get('face_bbox'),
                    'processing_notes': result.get('processing_notes', [])
                })
                
                logger.info(
                    f"✅ {scenario_name}: Quality={result['quality_score']:.2f}, "
                    f"Confidence={result['confidence']:.2f}, "
                    f"Detector={result.get('detector_used')}, "
                    f"Landmarks={'✓' if result.get('face_landmarks') else '✗'}"
                )
            else:
                test_result.update({
                    'error': result.get('error'),
                    'issues': result.get('issues', []),
                    'suggestions': result.get('suggestions', []),
                    'quality_score': result.get('quality_score', 0.0)
                })
                
                logger.warning(
                    f"❌ {scenario_name}: {result.get('error')}, "
                    f"Quality={result.get('quality_score', 0.0):.2f}"
                )
                
                if result.get('issues'):
                    logger.debug(f"Issues: {', '.join(result['issues'])}")
                if result.get('suggestions'):
                    logger.debug(f"Suggestions: {', '.join(result['suggestions'])}")
            
            return test_result
            
        except Exception as e:
            logger.error(f"❌ {scenario_name}: Exception - {e}")
            return {
                'scenario': scenario_name,
                'success': False,
                'error': str(e),
                'processing_time': (datetime.now() - start_time).total_seconds(),
                'timestamp': start_time.isoformat()
            }

    async def run_comprehensive_tests(self):
        """Run comprehensive test suite"""
        logger.info("🚀 Starting comprehensive enhanced face detection tests")
        
        # Create test images
        logger.info("Creating test image scenarios...")
        test_images = await self.create_test_images()
        
        # Run tests for each scenario
        logger.info(f"Running tests for {len(test_images)} scenarios...")
        
        for scenario, image_data in test_images.items():
            result = await self.test_scenario(scenario, image_data)
            self.test_results.append(result)
            
            # Small delay between tests
            await asyncio.sleep(0.5)
        
        # Generate comprehensive report
        await self.generate_report()

    async def generate_report(self):
        """Generate comprehensive test report"""
        logger.info("\n" + "="*80)
        logger.info("📊 ENHANCED FACE DETECTION TEST REPORT")
        logger.info("="*80)
        
        total_tests = len(self.test_results)
        successful_tests = sum(1 for r in self.test_results if r['success'])
        success_rate = successful_tests / total_tests if total_tests > 0 else 0
        
        logger.info(f"Total Tests: {total_tests}")
        logger.info(f"Successful: {successful_tests}")
        logger.info(f"Failed: {total_tests - successful_tests}")
        logger.info(f"Success Rate: {success_rate:.1%}")
        logger.info("")
        
        # Analyze successful detections
        successful_results = [r for r in self.test_results if r['success']]
        
        if successful_results:
            avg_quality = sum(r['quality_score'] for r in successful_results) / len(successful_results)
            avg_confidence = sum(r['confidence'] for r in successful_results) / len(successful_results)
            avg_processing_time = sum(r['processing_time'] for r in self.test_results) / len(self.test_results)
            
            landmarks_detected = sum(1 for r in successful_results if r.get('has_landmarks', False))
            landmarks_rate = landmarks_detected / len(successful_results)
            
            logger.info("📈 Performance Metrics:")
            logger.info(f"  Average Quality Score: {avg_quality:.2f}")
            logger.info(f"  Average Confidence: {avg_confidence:.2f}")
            logger.info(f"  Average Processing Time: {avg_processing_time:.3f}s")
            logger.info(f"  Landmarks Detection Rate: {landmarks_rate:.1%}")
            logger.info("")
            
            # Detector usage analysis
            detector_usage = {}
            for result in successful_results:
                detector = result.get('detector_used', 'unknown')
                detector_usage[detector] = detector_usage.get(detector, 0) + 1
            
            logger.info("🔍 Detector Usage:")
            for detector, count in sorted(detector_usage.items(), key=lambda x: x[1], reverse=True):
                percentage = count / len(successful_results) * 100
                logger.info(f"  {detector}: {count} times ({percentage:.1f}%)")
            logger.info("")
        
        # Analyze failures
        failed_results = [r for r in self.test_results if not r['success']]
        
        if failed_results:
            logger.info("❌ Failed Scenarios Analysis:")
            
            # Group failures by error type
            error_types = {}
            for result in failed_results:
                error = result.get('error', 'Unknown error')
                error_types[error] = error_types.get(error, 0) + 1
            
            for error, count in sorted(error_types.items(), key=lambda x: x[1], reverse=True):
                logger.info(f"  {error}: {count} occurrences")
            
            logger.info("")
            
            # Show specific failed scenarios with details
            logger.info("📋 Failed Scenario Details:")
            for result in failed_results:
                scenario = result['scenario']
                error = result.get('error', 'Unknown')
                quality = result.get('quality_score', 0.0)
                logger.info(f"  {scenario}: {error} (quality: {quality:.2f})")
                
                if result.get('suggestions'):
                    for suggestion in result['suggestions'][:2]:  # Show top 2 suggestions
                        logger.info(f"    💡 {suggestion}")
            
            logger.info("")
        
        # Performance recommendations
        logger.info("🎯 Recommendations:")
        
        if success_rate >= 0.8:
            logger.info("  ✅ Excellent detection performance!")
        elif success_rate >= 0.6:
            logger.info("  ⚠️  Good detection performance, minor improvements possible")
        else:
            logger.info("  🔧 Detection performance needs improvement")
        
        if successful_results:
            if avg_quality >= 0.7:
                logger.info("  ✅ High average quality scores")
            elif avg_quality >= 0.5:
                logger.info("  ⚠️  Moderate quality scores - consider image preprocessing")
            else:
                logger.info("  🔧 Low quality scores - improve image quality or detection parameters")
            
            if landmarks_rate >= 0.7:
                logger.info("  ✅ Good landmark detection rate")
            else:
                logger.info("  🔧 Consider installing more advanced detectors (RetinaFace, MTCNN)")
        
        if avg_processing_time > 2.0:
            logger.info("  ⚠️  Slow processing times - consider optimization")
        elif avg_processing_time > 1.0:
            logger.info("  ℹ️  Moderate processing times - acceptable for most use cases")
        else:
            logger.info("  ✅ Fast processing times")
        
        logger.info("")
        logger.info("📄 Detailed results saved to: test_results.json")
        
        # Save detailed results to JSON
        with open('test_results.json', 'w') as f:
            json.dump({
                'summary': {
                    'total_tests': total_tests,
                    'successful_tests': successful_tests,
                    'success_rate': success_rate,
                    'average_quality': avg_quality if successful_results else 0,
                    'average_confidence': avg_confidence if successful_results else 0,
                    'average_processing_time': avg_processing_time,
                    'landmarks_detection_rate': landmarks_rate if successful_results else 0,
                    'detector_usage': detector_usage if successful_results else {}
                },
                'detailed_results': self.test_results
            }, f, indent=2)
        
        logger.info("="*80)

    async def cleanup(self):
        """Cleanup resources"""
        await self.face_processor.cleanup()


async def main():
    """Main test function"""
    tester = EnhancedFaceDetectionTester()
    
    try:
        await tester.run_comprehensive_tests()
    except KeyboardInterrupt:
        logger.info("Tests interrupted by user")
    except Exception as e:
        logger.error(f"Test suite failed: {e}")
    finally:
        await tester.cleanup()


if __name__ == "__main__":
    asyncio.run(main())