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
from .worker_registry import worker_registry, WorkerInfo
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
        
        # Get worker HTTP port from capabilities, fallback to 8090
        http_port = 8090
        if worker.capabilities and "http_port" in worker.capabilities:
            http_port = worker.capabilities["http_port"]
        
        # Try IP address first, then hostname
        if worker.ip_address:
            return f"http://{worker.ip_address}:{http_port}"
        elif worker.hostname:
            return f"http://{worker.hostname}:{http_port}"
        
        return None
    
    async def start_camera_stream(self, camera_id: int, camera_type: str, rtsp_url: Optional[str] = None, device_index: Optional[int] = None) -> Dict[str, Any]:
        """Delegate camera streaming start to assigned worker"""
        camera_id_str = str(camera_id)
        
        # Find worker assigned to this camera
        worker_id = camera_delegation_service.get_camera_worker(camera_id)
        if not worker_id:
            # No worker assigned yet - try to find an available worker and assign camera
            logger.info(f"No worker assigned to camera {camera_id}, attempting auto-assignment")
            
            # Get available workers (basic check - could be improved)
            available_workers = []
            for worker in worker_registry.workers.values():
                if (worker.is_healthy and 
                    worker.status in ["idle", "online"] and
                    worker.site_id and
                    worker.worker_id not in camera_delegation_service.worker_cameras):
                    available_workers.append(worker)
            
            if not available_workers:
                return {
                    "success": False,
                    "error": "No available workers to assign camera",
                    "camera_id": camera_id
                }
            
            # Try to assign camera to first available worker
            # In a production system, this would be more sophisticated
            worker_id = available_workers[0].worker_id
            logger.info(f"Attempting to assign camera {camera_id} to worker {worker_id}")
            
            # Update in-memory assignment (simplified)
            camera_delegation_service.assignments[camera_id] = worker_id
            camera_delegation_service.worker_cameras[worker_id] = camera_id
            
            # Update worker info
            available_workers[0].camera_id = camera_id
        
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
            command_id = worker_command_service.send_command(
                worker_id=worker_id,
                command=WorkerCommand.ASSIGN_CAMERA,
                parameters={
                    "camera_id": camera_id,
                    "camera_type": camera_type,
                    "rtsp_url": rtsp_url,
                    "device_index": device_index
                }
            )
            
            if command_id:
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
                            
                            # Broadcast status change
                            await self._broadcast_camera_status_change(camera_id, True, worker_id)
                            return {
                                "success": True,
                                "message": result.get("message", "Camera stream started"),
                                "camera_id": camera_id,
                                "worker_id": worker_id,
                                "worker_endpoint": endpoint
                            }
                    except Exception as http_error:
                        logger.warning(f"Direct HTTP call to worker failed: {http_error}")
                
                # Fallback to command result - still broadcast status change
                await self._broadcast_camera_status_change(camera_id, True, worker_id)
                return {
                    "success": True,
                    "message": "Camera stream start command sent to worker",
                    "camera_id": camera_id,
                    "worker_id": worker_id,
                    "command_id": command_id
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to send start command to worker",
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
            command_id = worker_command_service.send_command(
                worker_id=worker_id,
                command=WorkerCommand.RELEASE_CAMERA,
                parameters={"camera_id": camera_id}
            )
            
            if command_id:
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
                            
                            # Broadcast status change
                            await self._broadcast_camera_status_change(camera_id, False, worker_id)
                            return {
                                "success": True,
                                "message": result.get("message", "Camera stream stopped"),
                                "camera_id": camera_id,
                                "worker_id": worker_id
                            }
                    except Exception as http_error:
                        logger.warning(f"Direct HTTP call to worker failed: {http_error}")
                
                # Fallback to command result - still broadcast status change
                await self._broadcast_camera_status_change(camera_id, False, worker_id)
                return {
                    "success": True,
                    "message": "Camera stream stop command sent to worker",
                    "camera_id": camera_id,
                    "worker_id": worker_id,
                    "command_id": command_id
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to send stop command to worker",
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
        
        # First check worker's reported streaming status from heartbeat
        streaming_status = self._get_streaming_status_from_worker(worker, camera_id)
        
        # Try direct HTTP call to worker as fallback
        endpoint = self._get_worker_endpoint(worker_id)
        if endpoint and self.http_client:
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
                    # Use streaming status from heartbeat if HTTP call fails
                    streaming_status.update({
                        "error": f"Worker HTTP status {response.status_code}, using heartbeat data"
                    })
                    return streaming_status
                    
            except httpx.TimeoutException:
                # Use streaming status from heartbeat on timeout
                streaming_status.update({
                    "error": "Worker request timeout, using heartbeat data"
                })
                return streaming_status
            except Exception as e:
                # Use streaming status from heartbeat on error
                streaming_status.update({
                    "error": f"Worker communication error: {str(e)}, using heartbeat data"
                })
                return streaming_status
        else:
            # No endpoint available, use heartbeat data
            streaming_status.update({
                "error": "Worker endpoint not available, using heartbeat data"
            })
            return streaming_status
    
    def _get_streaming_status_from_worker(self, worker: WorkerInfo, camera_id: int) -> Dict[str, Any]:
        """Get streaming and processing status from worker's heartbeat data"""
        camera_id_str = str(camera_id)
        
        # Check if worker has streaming capabilities info
        streaming_active = False
        if (worker.capabilities and 
            "active_camera_streams" in worker.capabilities and
            isinstance(worker.capabilities["active_camera_streams"], list)):
            
            active_streams = worker.capabilities["active_camera_streams"]
            streaming_active = camera_id_str in active_streams
        
        # Check if worker has processing capabilities info
        processing_active = False
        if (worker.capabilities and 
            "active_camera_processing" in worker.capabilities and
            isinstance(worker.capabilities["active_camera_processing"], list)):
            
            active_processing = worker.capabilities["active_camera_processing"]
            processing_active = camera_id_str in active_processing
        
        return {
            "camera_id": camera_id,
            "stream_active": streaming_active,
            "processing_active": processing_active,
            "worker_id": worker.worker_id,
            "worker_status": worker.status.value,
            "worker_healthy": worker.is_healthy,
            "source": "heartbeat",
            "total_active_streams": worker.capabilities.get("total_active_streams", 0) if worker.capabilities else 0,
            "total_active_processing": worker.capabilities.get("total_active_processing", 0) if worker.capabilities else 0,
            "streaming_status_updated": worker.capabilities.get("streaming_status_updated") if worker.capabilities else None,
            "processing_status_updated": worker.capabilities.get("processing_status_updated") if worker.capabilities else None
        }
    
    async def proxy_camera_stream(self, camera_id: int) -> AsyncGenerator[bytes, None]:
        """Proxy MJPEG stream from worker to client"""
        logger.info(f"Starting proxy stream for camera {camera_id}")
        
        worker_id = camera_delegation_service.get_camera_worker(camera_id)
        if not worker_id:
            logger.error(f"No worker assigned to camera {camera_id}")
            raise ValueError("No worker assigned to camera")
        
        logger.info(f"Camera {camera_id} assigned to worker {worker_id}")
        
        worker = worker_registry.get_worker(worker_id)
        if not worker:
            logger.error(f"Worker {worker_id} not found in registry")
            raise ValueError("Assigned worker is not available")
        
        if not worker.is_healthy:
            logger.error(f"Worker {worker_id} is not healthy (status: {worker.status})")
            raise ValueError("Assigned worker is not available")
        
        logger.info(f"Worker {worker_id} is healthy, getting endpoint")
        
        endpoint = self._get_worker_endpoint(worker_id)
        if not endpoint:
            logger.error(f"No endpoint available for worker {worker_id}")
            raise ValueError("Worker endpoint not available")
        
        logger.info(f"Worker {worker_id} endpoint: {endpoint}")
        
        if not self.http_client:
            logger.error("HTTP client not initialized")
            raise ValueError("HTTP client not initialized")
        
        stream_url = f"{endpoint}/cameras/{camera_id}/stream/feed"
        logger.info(f"Attempting to proxy stream from: {stream_url}")
        
        try:
            async with self.http_client.stream(
                "GET",
                stream_url,
                timeout=None  # No timeout for streaming
            ) as response:
                logger.info(f"Worker stream response status: {response.status_code}")
                
                if response.status_code != 200:
                    response_text = await response.aread()
                    logger.error(f"Worker stream returned status {response.status_code}, body: {response_text[:500]}")
                    raise ValueError(f"Worker stream returned status {response.status_code}")
                
                logger.info(f"Successfully connected to worker stream, starting proxy")
                chunk_count = 0
                async for chunk in response.aiter_bytes():
                    chunk_count += 1
                    if chunk_count % 100 == 0:  # Log every 100 chunks
                        logger.debug(f"Proxied {chunk_count} chunks for camera {camera_id}")
                    yield chunk
                    
        except httpx.ConnectError as e:
            logger.error(f"Failed to connect to worker {worker_id} at {endpoint}: {e}")
            raise ValueError("Failed to connect to worker")
        except httpx.TimeoutException as e:
            logger.error(f"Worker stream timeout for worker {worker_id}: {e}")
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

    async def _broadcast_camera_status_change(self, camera_id: int, is_streaming: bool, worker_id: str):
        """Broadcast camera status change to SSE clients"""
        try:
            from .camera_status_broadcaster import camera_status_broadcaster
            from ..core.database import db
            from ..models.database import Camera
            from sqlalchemy import select
            
            # Get site_id for this camera using the correct database access pattern
            async with db.get_session() as db_session:
                result = await db_session.execute(
                    select(Camera.site_id, Camera.tenant_id).where(Camera.camera_id == camera_id)
                )
                camera_info = result.first()
                
                if camera_info:
                    site_id_str = str(camera_info.site_id)
                    
                    status_data = {
                        "camera_id": camera_id,
                        "stream_active": is_streaming,
                        "worker_id": worker_id,
                        "timestamp": datetime.utcnow().isoformat(),
                        "source": "proxy_service"
                    }
                    
                    await camera_status_broadcaster.broadcast_camera_status_change(
                        site_id_str, camera_id, status_data
                    )
                    
                    logger.debug(f"Broadcasted camera {camera_id} status change: streaming={is_streaming}")
                    
        except Exception as e:
            logger.error(f"Failed to broadcast camera status change: {e}")


# Global camera proxy service
camera_proxy_service = CameraProxyService()