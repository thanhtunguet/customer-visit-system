"""
Camera Proxy Service - Delegates camera operations to workers
Replaces direct camera streaming with worker delegation and proxy functionality
"""
import asyncio
import logging
import httpx
from typing import Dict, Optional, Any, AsyncGenerator
from datetime import datetime, timedelta

from .camera_delegation_service import camera_delegation_service
from .worker_registry import worker_registry
from .worker_command_service import worker_command_service
from common.enums.worker import WorkerStatus
from common.enums.commands import WorkerCommand

logger = logging.getLogger(__name__)


class CameraProxyService:
    """Service for proxying camera operations to workers"""
    
    def __init__(self):
        self.http_client: Optional[httpx.AsyncClient] = None
        self.worker_endpoints: Dict[str, str] = {}  # worker_id -> http endpoint
        self.proxy_timeout = 30.0  # Timeout for worker HTTP requests
        
    async def initialize(self):
        """Initialize the proxy service"""
        self.http_client = httpx.AsyncClient(timeout=self.proxy_timeout)
        logger.info("Camera proxy service initialized")
    
    async def shutdown(self):
        """Shutdown the proxy service"""
        if self.http_client:
            await self.http_client.aclose()
        logger.info("Camera proxy service shutdown")
    
    def _get_worker_endpoint(self, worker_id: str) -> Optional[str]:
        """Get HTTP endpoint for a worker"""
        worker = worker_registry.get_worker(worker_id)
        if not worker:
            return None
        
        # Get worker HTTP endpoint (assuming workers expose HTTP on port 8090)
        # In production, this would be configurable or discovered
        if worker.hostname:
            return f"http://{worker.hostname}:8090"
        
        return None
    
    async def start_camera_stream(self, camera_id: int, camera_type: str, rtsp_url: Optional[str] = None, device_index: Optional[int] = None) -> Dict[str, Any]:
        """Delegate camera streaming start to assigned worker"""
        camera_id_str = str(camera_id)
        
        # Find worker assigned to this camera
        worker_id = camera_delegation_service.get_camera_worker(camera_id)
        if not worker_id:
            return {
                "success": False,
                "error": "No worker assigned to camera",
                "camera_id": camera_id
            }
        
        worker = worker_registry.get_worker(worker_id)
        if not worker or not worker.is_healthy:
            return {
                "success": False,
                "error": "Assigned worker is not available",
                "worker_id": worker_id,
                "camera_id": camera_id
            }
        
        try:
            # Send command to worker to start streaming
            command_result = await worker_command_service.send_command(
                worker_id=worker_id,
                command=WorkerCommand.ASSIGN_CAMERA,
                parameters={
                    "camera_id": camera_id,
                    "camera_type": camera_type,
                    "rtsp_url": rtsp_url,
                    "device_index": device_index
                }
            )
            
            if command_result.get("success"):
                # Also try direct HTTP call to worker for immediate response
                endpoint = self._get_worker_endpoint(worker_id)
                if endpoint and self.http_client:
                    try:
                        response = await self.http_client.post(
                            f"{endpoint}/cameras/{camera_id}/stream/start",
                            json={
                                "camera_type": camera_type,
                                "rtsp_url": rtsp_url,
                                "device_index": device_index
                            },
                            timeout=10.0
                        )
                        if response.status_code == 200:
                            result = response.json()
                            logger.info(f"Successfully started camera {camera_id} streaming on worker {worker_id}")
                            return {
                                "success": True,
                                "message": result.get("message", "Camera stream started"),
                                "camera_id": camera_id,
                                "worker_id": worker_id,
                                "worker_endpoint": endpoint
                            }
                    except Exception as http_error:
                        logger.warning(f"Direct HTTP call to worker failed: {http_error}")
                
                # Fallback to command result
                return {
                    "success": True,
                    "message": "Camera stream start command sent to worker",
                    "camera_id": camera_id,
                    "worker_id": worker_id,
                    "command_id": command_result.get("command_id")
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to send start command to worker: {command_result.get('error')}",
                    "camera_id": camera_id,
                    "worker_id": worker_id
                }
                
        except Exception as e:
            logger.error(f"Error starting camera stream on worker: {e}")
            return {
                "success": False,
                "error": f"Worker communication error: {str(e)}",
                "camera_id": camera_id,
                "worker_id": worker_id
            }
    
    async def stop_camera_stream(self, camera_id: int) -> Dict[str, Any]:
        """Delegate camera streaming stop to assigned worker"""
        camera_id_str = str(camera_id)
        
        # Find worker assigned to this camera
        worker_id = camera_delegation_service.get_camera_worker(camera_id)
        if not worker_id:
            return {
                "success": False,
                "error": "No worker assigned to camera",
                "camera_id": camera_id
            }
        
        try:
            # Send command to worker to stop streaming
            command_result = await worker_command_service.send_command(
                worker_id=worker_id,
                command=WorkerCommand.RELEASE_CAMERA,
                parameters={"camera_id": camera_id}
            )
            
            if command_result.get("success"):
                # Also try direct HTTP call to worker
                endpoint = self._get_worker_endpoint(worker_id)
                if endpoint and self.http_client:
                    try:
                        response = await self.http_client.post(
                            f"{endpoint}/cameras/{camera_id}/stream/stop"
                        )
                        if response.status_code == 200:
                            result = response.json()
                            logger.info(f"Successfully stopped camera {camera_id} streaming on worker {worker_id}")
                            return {
                                "success": True,
                                "message": result.get("message", "Camera stream stopped"),
                                "camera_id": camera_id,
                                "worker_id": worker_id
                            }
                    except Exception as http_error:
                        logger.warning(f"Direct HTTP call to worker failed: {http_error}")
                
                # Fallback to command result
                return {
                    "success": True,
                    "message": "Camera stream stop command sent to worker",
                    "camera_id": camera_id,
                    "worker_id": worker_id,
                    "command_id": command_result.get("command_id")
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to send stop command to worker: {command_result.get('error')}",
                    "camera_id": camera_id,
                    "worker_id": worker_id
                }
                
        except Exception as e:
            logger.error(f"Error stopping camera stream on worker: {e}")
            return {
                "success": False,
                "error": f"Worker communication error: {str(e)}",
                "camera_id": camera_id,
                "worker_id": worker_id
            }
    
    async def get_camera_stream_status(self, camera_id: int) -> Dict[str, Any]:
        """Get camera streaming status from assigned worker"""
        worker_id = camera_delegation_service.get_camera_worker(camera_id)
        if not worker_id:
            return {
                "camera_id": camera_id,
                "stream_active": False,
                "error": "No worker assigned to camera",
                "worker_id": None
            }
        
        worker = worker_registry.get_worker(worker_id)
        if not worker:
            return {
                "camera_id": camera_id,
                "stream_active": False,
                "error": "Assigned worker not found",
                "worker_id": worker_id
            }
        
        endpoint = self._get_worker_endpoint(worker_id)
        if not endpoint or not self.http_client:
            return {
                "camera_id": camera_id,
                "stream_active": False,
                "error": "Worker endpoint not available",
                "worker_id": worker_id,
                "worker_status": worker.status.value
            }
        
        try:
            response = await self.http_client.get(
                f"{endpoint}/cameras/{camera_id}/stream/status",
                timeout=5.0
            )
            if response.status_code == 200:
                result = response.json()
                result.update({
                    "worker_id": worker_id,
                    "worker_status": worker.status.value,
                    "worker_healthy": worker.is_healthy
                })
                return result
            else:
                return {
                    "camera_id": camera_id,
                    "stream_active": False,
                    "error": f"Worker returned status {response.status_code}",
                    "worker_id": worker_id,
                    "worker_status": worker.status.value
                }
                
        except httpx.TimeoutException:
            return {
                "camera_id": camera_id,
                "stream_active": False,
                "error": "Worker request timeout",
                "worker_id": worker_id,
                "worker_status": worker.status.value
            }
        except Exception as e:
            return {
                "camera_id": camera_id,
                "stream_active": False,
                "error": f"Worker communication error: {str(e)}",
                "worker_id": worker_id,
                "worker_status": worker.status.value if worker else "unknown"
            }
    
    async def proxy_camera_stream(self, camera_id: int) -> AsyncGenerator[bytes, None]:
        """Proxy MJPEG stream from worker to client"""
        worker_id = camera_delegation_service.get_camera_worker(camera_id)
        if not worker_id:
            raise ValueError("No worker assigned to camera")
        
        worker = worker_registry.get_worker(worker_id)
        if not worker or not worker.is_healthy:
            raise ValueError("Assigned worker is not available")
        
        endpoint = self._get_worker_endpoint(worker_id)
        if not endpoint:
            raise ValueError("Worker endpoint not available")
        
        if not self.http_client:
            raise ValueError("HTTP client not initialized")
        
        try:
            async with self.http_client.stream(
                "GET",
                f"{endpoint}/cameras/{camera_id}/stream/feed",
                timeout=None  # No timeout for streaming
            ) as response:
                if response.status_code != 200:
                    raise ValueError(f"Worker stream returned status {response.status_code}")
                
                async for chunk in response.aiter_bytes():
                    yield chunk
                    
        except httpx.ConnectError:
            raise ValueError("Failed to connect to worker")
        except httpx.TimeoutException:
            raise ValueError("Worker stream timeout")
        except Exception as e:
            logger.error(f"Error proxying stream from worker {worker_id}: {e}")
            raise ValueError(f"Stream proxy error: {str(e)}")
    
    async def get_streaming_debug_info(self) -> Dict[str, Any]:
        """Get debug information about all camera streaming across workers"""
        debug_info = {
            "proxy_service_status": "active",
            "total_assignments": len(camera_delegation_service.assignments),
            "worker_endpoints": {},
            "camera_statuses": {}
        }
        
        # Get all camera assignments
        assignments = camera_delegation_service.list_assignments()
        
        for camera_id_str, assignment_info in assignments.items():
            camera_id = int(camera_id_str)
            worker_id = assignment_info["worker_id"]
            
            # Get worker endpoint
            endpoint = self._get_worker_endpoint(worker_id)
            debug_info["worker_endpoints"][worker_id] = endpoint
            
            # Get camera status from worker
            try:
                camera_status = await self.get_camera_stream_status(camera_id)
                debug_info["camera_statuses"][camera_id] = camera_status
            except Exception as e:
                debug_info["camera_statuses"][camera_id] = {
                    "camera_id": camera_id,
                    "error": f"Failed to get status: {str(e)}",
                    "worker_id": worker_id
                }
        
        return debug_info
    
    def is_camera_streaming(self, camera_id: int) -> bool:
        """Quick check if camera has a worker assigned (doesn't verify actual streaming)"""
        worker_id = camera_delegation_service.get_camera_worker(camera_id)
        if not worker_id:
            return False
        
        worker = worker_registry.get_worker(worker_id)
        return worker is not None and worker.is_healthy


# Global camera proxy service
camera_proxy_service = CameraProxyService()