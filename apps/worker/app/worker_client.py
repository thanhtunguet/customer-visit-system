from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
import time
from datetime import datetime, timezone
from typing import Dict, Optional, Any

import httpx
from pydantic import BaseModel

from common.enums.worker import WorkerStatus
from common.enums.commands import WorkerCommand
from .worker_id_manager import worker_id_manager

logger = logging.getLogger(__name__)


class WorkerClient:
    """Client for managing worker registration and heartbeat with backend API"""
    
    def __init__(self, config):
        self.config = config
        self.http_client: Optional[httpx.AsyncClient] = None
        self.access_token: Optional[str] = None
        self.token_expires_at: float = 0
        self.worker_id: Optional[str] = None
        self.heartbeat_task: Optional[asyncio.Task] = None
        self.faces_processed_since_heartbeat = 0
        self.registration_retry_count = 0
        self.max_registration_retries = 5
        
        # Camera assignment from backend
        self.assigned_camera_id: Optional[int] = None
        self.assigned_camera_name: Optional[str] = None
        self.camera_config: Optional[Dict[str, Any]] = None
        
        # Shutdown signaling
        self.shutdown_requested = False
        self.shutdown_signal = None
        
        # Worker info
        self.hostname = socket.gethostname()
        self.worker_name = f"Worker-{self.hostname}"
        self.worker_version = "1.0.0"
        self.capabilities = {
            "detector_type": config.detector_type,
            "embedder_type": config.embedder_type,
            "mock_mode": config.mock_mode,
            "fps": config.worker_fps,
            "camera_source": "rtsp" if config.rtsp_url else "usb",
            # HTTP server removed - worker operates via socket communication only
            "streaming_enabled": True,
            "face_processing_enabled": True
        }
        
        # Streaming service reference (set from parent worker)
        self.streaming_service = None
    
    def set_streaming_service(self, streaming_service):
        """Set reference to streaming service for status checks"""
        self.streaming_service = streaming_service
        
    def _get_current_worker_status(self) -> WorkerStatus:
        """Determine current worker status based on camera assignment"""
        # If we have a camera assigned, we should be PROCESSING 
        # (the worker should be actively streaming and processing)
        if self.assigned_camera_id:
            return WorkerStatus.PROCESSING
            
        # No camera assigned - worker is idle
        return WorkerStatus.IDLE
    
    def _parse_site_id(self) -> Optional[int]:
        """Parse site_id from config, handling both integer strings and s-prefixed values"""
        if not self.config.site_id:
            return None
        
        site_id_str = str(self.config.site_id).strip()
        
        # Handle direct integer strings
        if site_id_str.isdigit():
            return int(site_id_str)
        
        # Handle s-prefixed format like "s-1"
        if site_id_str.startswith("s-") and site_id_str[2:].isdigit():
            return int(site_id_str[2:])
        
        logger.warning(f"Invalid site_id format: {site_id_str}, expected integer or 's-N' format")
        return None
    
    async def initialize(self):
        """Initialize worker client and register with backend"""
        self.http_client = httpx.AsyncClient(timeout=30.0)
        
        # Log environment info for debugging
        env_worker_id = os.getenv("WORKER_ID")
        if env_worker_id:
            logger.info(f"WORKER_ID environment variable detected: {env_worker_id}")
        else:
            logger.info("No WORKER_ID environment variable set, will use .env file or auto-generate")
        
        # Register with backend
        await self._register_worker()
        
        # Start heartbeat task
        if self.worker_id:
            self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            logger.info(f"Worker client initialized with final ID: {self.worker_id}")
        else:
            logger.error("Failed to register worker, heartbeat not started")
    
    async def shutdown(self):
        """Cleanup worker client with aggressive timeouts"""
        logger.info("Starting worker client shutdown...")
        
        # Set shutdown flag immediately
        self.shutdown_requested = True
        
        # Cancel heartbeat task immediately
        if self.heartbeat_task and not self.heartbeat_task.done():
            logger.info("Cancelling heartbeat task...")
            self.heartbeat_task.cancel()
            try:
                await asyncio.wait_for(self.heartbeat_task, timeout=0.5)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
            logger.info("Heartbeat task cancelled")
        
        # Try to send offline status with very short timeout - max 3 attempts as mentioned in log
        if self.worker_id:
            max_attempts = 3
            for attempt in range(max_attempts):
                try:
                    logger.info(f"Sending offline status (attempt {attempt + 1}/{max_attempts})")
                    await asyncio.wait_for(
                        self._send_heartbeat(status=WorkerStatus.OFFLINE),
                        timeout=1.0  # Very short timeout per attempt
                    )
                    logger.info("Successfully sent offline status to backend")
                    break
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout sending offline status (attempt {attempt + 1})")
                    if attempt == max_attempts - 1:
                        logger.warning("Max attempts reached, proceeding with shutdown")
                except Exception as e:
                    logger.warning(f"Failed to send offline status (attempt {attempt + 1}): {e}")
                    if attempt == max_attempts - 1:
                        logger.warning("Max attempts reached, proceeding with shutdown")
        
        # Close HTTP client with very short timeout
        if self.http_client:
            try:
                logger.info("Closing HTTP client...")
                await asyncio.wait_for(self.http_client.aclose(), timeout=0.5)
                logger.info("HTTP client closed successfully")
            except asyncio.TimeoutError:
                logger.warning("HTTP client close timeout - forcing close")
                # Force close without waiting
                try:
                    self.http_client._client.close()
                except:
                    pass
            except Exception as e:
                logger.warning(f"Error closing HTTP client: {e}")
        
        logger.info("Worker client shutdown complete")
    
    async def clear_persistent_id(self):
        """Clear the persistent worker ID (for complete shutdown/reset)"""
        try:
            worker_id_manager.clear_worker_id()
            logger.info("Cleared persistent worker ID")
        except Exception as e:
            logger.warning(f"Failed to clear persistent worker ID: {e}")
    
    async def _authenticate(self):
        """Get JWT token for API access"""
        try:
            response = await self.http_client.post(
                f"{self.config.api_url}/v1/auth/token",
                json={
                    "grant_type": "api_key",
                    "api_key": self.config.worker_api_key,
                    "tenant_id": self.config.tenant_id,
                    "role": "worker",
                }
            )
            response.raise_for_status()
            
            data = response.json()
            self.access_token = data["access_token"]
            self.token_expires_at = time.time() + 3500  # Refresh before expiry
            
            logger.debug("Successfully authenticated with API")
            return True
            
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            return False
    
    async def _ensure_authenticated(self):
        """Ensure we have a valid token"""
        if time.time() >= self.token_expires_at:
            await self._authenticate()
    
    async def _register_worker(self):
        """Register worker with consolidated API"""
        # Get or create persistent worker ID
        persistent_worker_id = worker_id_manager.get_or_create_worker_id(
            tenant_id=self.config.tenant_id,
            site_id=str(self.config.site_id) if self.config.site_id else None
        )
        
        # Keep track of our intended worker ID (especially important for env vars)
        intended_worker_id = persistent_worker_id
        logger.info(f"Registering worker with intended ID: {intended_worker_id}")
        
        for attempt in range(self.max_registration_retries):
            try:
                # Authenticate first
                if not await self._authenticate():
                    continue
                
                registration_data = {
                    "worker_id": intended_worker_id,  # Use our intended ID
                    "worker_name": self.worker_name,
                    "hostname": self.hostname,
                    "worker_version": self.worker_version,
                    "capabilities": self.capabilities,
                    "site_id": self._parse_site_id(),
                    "is_reconnection": self.worker_id is not None,  # Flag for API to know this is a reconnection
                }
                
                # Use consolidated worker API
                response = await self.http_client.post(
                    f"{self.config.api_url}/v1/workers/register",
                    json=registration_data,
                    headers={"Authorization": f"Bearer {self.access_token}"}
                )
                response.raise_for_status()
                
                result = response.json()
                
                # Use our intended worker ID, not what backend returns
                # This ensures environment variables and .env file WORKER_IDs are respected
                backend_worker_id = result.get("worker_id")
                if backend_worker_id and backend_worker_id != intended_worker_id:
                    logger.warning(f"Backend returned different worker_id ({backend_worker_id}), keeping intended ID ({intended_worker_id})")
                
                self.worker_id = intended_worker_id  # Always use our intended ID
                
                # Capture camera assignment from backend response
                if "assigned_camera_id" in result and result["assigned_camera_id"]:
                    self.assigned_camera_id = int(result["assigned_camera_id"])
                    logger.info(f"Worker assigned camera {self.assigned_camera_id} during registration")
                else:
                    self.assigned_camera_id = None
                    logger.info("Worker registered but no camera assigned")
                
                # Update persistent storage with successful registration
                worker_id_manager.update_last_used(
                    worker_id=self.worker_id,
                    tenant_id=self.config.tenant_id,
                    site_id=str(self.config.site_id) if self.config.site_id else None
                )
                
                status = "reconnected" if registration_data["is_reconnection"] else "registered"
                logger.info(f"Worker {status} successfully with consolidated API - ID {self.worker_id}: {result.get('message', 'Success')}")
                return
                
            except Exception as e:
                logger.error(f"Worker registration failed (attempt {attempt + 1}/{self.max_registration_retries}): {e}")
                
                # If we're using a persistent worker ID and getting 404/403 errors, 
                # it might be stale - try clearing it on the last attempt
                if (attempt == self.max_registration_retries - 1 and 
                    intended_worker_id and 
                    hasattr(e, 'response') and 
                    e.response and e.response.status_code in [404, 403]):
                    logger.warning("Clearing potentially stale worker ID for fresh registration")
                    worker_id_manager.clear_worker_id()
                    # Create a new ID for potential retry
                    intended_worker_id = worker_id_manager.get_or_create_worker_id(
                        tenant_id=self.config.tenant_id,
                        site_id=str(self.config.site_id) if self.config.site_id else None
                    )
                
                if attempt < self.max_registration_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    await asyncio.sleep(wait_time)
        
        logger.error(f"Failed to register worker after {self.max_registration_retries} attempts")
        raise RuntimeError("Worker registration failed")
    
    async def _send_heartbeat(self, status: WorkerStatus = WorkerStatus.IDLE):
        """Send heartbeat to consolidated API"""
        if not self.worker_id:
            logger.warning("Cannot send heartbeat - worker not registered")
            return
        
        try:
            await self._ensure_authenticated()
            
            # Get current capabilities with dynamic streaming status
            current_capabilities = self._get_current_capabilities()
            
            heartbeat_data = {
                "status": status.value,
                "faces_processed_count": self.faces_processed_since_heartbeat,
                "capabilities": current_capabilities,
                "current_camera_id": self.assigned_camera_id,
            }
            
            # Add error message if we're in error state
            if hasattr(self, '_last_error') and self._last_error:
                heartbeat_data["error_message"] = self._last_error
            
            # Use consolidated worker API
            response = await self.http_client.post(
                f"{self.config.api_url}/v1/workers/{self.worker_id}/heartbeat",
                json=heartbeat_data,
                headers={"Authorization": f"Bearer {self.access_token}"},
                timeout=5.0
            )
            response.raise_for_status()
            
            result = response.json()
            
            # Reset faces processed count after successful heartbeat
            self.faces_processed_since_heartbeat = 0
            
            # Update camera assignment if backend provides it
            backend_camera_id = result.get("assigned_camera_id")
            if backend_camera_id != self.assigned_camera_id:
                if backend_camera_id:
                    logger.info(f"Backend updated camera assignment: {self.assigned_camera_id} → {backend_camera_id}")
                    self.assigned_camera_id = backend_camera_id
                else:
                    logger.info("Backend removed camera assignment")
                    self.assigned_camera_id = None
            
            logger.debug(f"Heartbeat sent successfully to consolidated API - status: {status.value}")
            
        except Exception as e:
            logger.error(f"Failed to send heartbeat to consolidated API: {e}")

    
    def _get_current_capabilities(self) -> dict:
        """Get current capabilities with dynamic streaming status"""
        current_capabilities = self.capabilities.copy()
        
        # Update streaming status based on current state
        if self.streaming_service:
            try:
                # Get streaming status from streaming service
                active_streams = self.streaming_service.get_active_streams()
                current_capabilities.update({
                    "active_camera_streams": list(active_streams.keys()),
                    "total_active_streams": len(active_streams),
                    "streaming_status_updated": datetime.utcnow().isoformat(),
                })
            except Exception as e:
                logger.debug(f"Could not get streaming status: {e}")
                current_capabilities.update({
                    "active_camera_streams": [],
                    "total_active_streams": 0,
                    "streaming_status_updated": datetime.utcnow().isoformat(),
                })
        else:
            # No streaming service - determine from worker status and camera assignment
            worker_status = self._get_current_worker_status()
            
            # If worker is PROCESSING and has a camera assigned, it's streaming
            if worker_status == WorkerStatus.PROCESSING and self.assigned_camera_id:
                current_capabilities.update({
                    "active_camera_streams": [str(self.assigned_camera_id)],
                    "total_active_streams": 1,
                    "streaming_status_updated": datetime.utcnow().isoformat(),
                })
            else:
                current_capabilities.update({
                    "active_camera_streams": [],
                    "total_active_streams": 0,
                    "streaming_status_updated": datetime.utcnow().isoformat(),
                })
        
        return current_capabilities
            # Don't raise - heartbeat failures shouldn't crash the worker
    
    async def _heartbeat_loop(self):
        """Main heartbeat loop"""
        heartbeat_interval = 30  # 30 seconds
        
        while True:
            try:
                # Send heartbeat with dynamic status detection
                await self._send_heartbeat()
                
                # Check if shutdown was requested
                if self.should_shutdown():
                    logger.warning("Shutdown requested - stopping heartbeat loop")
                    break
                
                await asyncio.sleep(heartbeat_interval)
                
            except asyncio.CancelledError:
                logger.info("Heartbeat loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}")
                await asyncio.sleep(heartbeat_interval)
    
    def report_face_processed(self):
        """Report that a face was processed"""
        self.faces_processed_since_heartbeat += 1
    
    async def report_error(self, error_message: str):
        """Report error status to backend"""
        await self._send_heartbeat(status=WorkerStatus.ERROR, error_message=error_message)
    
    async def report_maintenance(self):
        """Report maintenance status to backend"""
        await self._send_heartbeat(status=WorkerStatus.MAINTENANCE)
    
    async def report_processing(self):
        """Report that worker is currently processing faces"""
        await self._send_heartbeat(status=WorkerStatus.PROCESSING)
    
    async def report_idle(self):
        """Report that worker is idle and ready for work"""
        await self._send_heartbeat(status=WorkerStatus.IDLE)
    
    async def request_camera_assignment(self):
        """
        Request camera assignment using consolidated API.
        """
        if not self.worker_id:
            logger.warning("Cannot request camera assignment - worker not registered")
            return None
        
        try:
            await self._ensure_authenticated()
            
            # Use consolidated worker API
            response = await self.http_client.post(
                f"{self.config.api_url}/v1/workers/{self.worker_id}/camera/request",
                json={"site_id": self.config.site_id},
                headers={"Authorization": f"Bearer {self.access_token}"}
            )
            response.raise_for_status()
            
            result = response.json()
            if result.get("assigned") and result.get("camera_id"):
                self.assigned_camera_id = int(result["camera_id"])
                self.assigned_camera_name = result.get("camera_name")
                logger.info(f"Camera assignment requested successfully: {self.assigned_camera_id} ({self.assigned_camera_name})")
                return self.assigned_camera_id
            else:
                logger.info(f"Camera assignment requested but not available: {result.get('message')}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to request camera assignment from consolidated API: {e}")
            return None
    
    def get_assigned_camera(self) -> Optional[int]:
        """Get currently assigned camera ID"""
        return self.assigned_camera_id
    
    async def _check_shutdown_signal(self):
        """Check for pending shutdown signals from backend"""
        try:
            response = await self.http_client.post(
                f"{self.config.api_url}/v1/workers/{self.worker_id}/shutdown-signal",
                headers={"Authorization": f"Bearer {self.access_token}"}
            )
            response.raise_for_status()
            
            result = response.json()
            if result.get("has_shutdown_signal"):
                shutdown_signal = result.get("shutdown_signal")
                if shutdown_signal:
                    self.shutdown_requested = True
                    self.shutdown_signal = shutdown_signal
                    
                    logger.warning(f"Shutdown signal received: {shutdown_signal['signal']}")
                    logger.warning(f"Requested by: {shutdown_signal['requested_by']}")
                    logger.warning(f"Message: {shutdown_signal['message']}")
                    
                    # Acknowledge receipt
                    await self._acknowledge_shutdown()
                    
        except Exception as e:
            logger.debug(f"Error checking shutdown signal: {e}")
    
    async def _acknowledge_shutdown(self):
        """Acknowledge receipt of shutdown signal"""
        try:
            response = await self.http_client.post(
                f"{self.config.api_url}/v1/workers/{self.worker_id}/acknowledge-shutdown",
                headers={"Authorization": f"Bearer {self.access_token}"}
            )
            response.raise_for_status()
            logger.info("Shutdown signal acknowledged")
            
        except Exception as e:
            logger.error(f"Failed to acknowledge shutdown: {e}")
    
    async def complete_shutdown(self):
        """Mark shutdown as completed before exiting"""
        try:
            response = await self.http_client.post(
                f"{self.config.api_url}/v1/workers/{self.worker_id}/complete-shutdown",
                headers={"Authorization": f"Bearer {self.access_token}"}
            )
            response.raise_for_status()
            logger.info("Shutdown completion reported to backend")
            
        except Exception as e:
            logger.error(f"Failed to report shutdown completion: {e}")
    
    def should_shutdown(self) -> bool:
        """Check if worker should shutdown"""
        return self.shutdown_requested
    
    def get_shutdown_signal(self) -> Optional[dict]:
        """Get shutdown signal details"""
        return self.shutdown_signal
    
    def get_camera_config(self) -> Optional[Dict[str, Any]]:
        """Get current camera configuration"""
        return self.camera_config

    def set_camera_assignment_callback(self, callback):
        """Set callback for camera assignment events"""
        self._camera_assignment_callback = callback
    
    def set_camera_release_callback(self, callback):
        """Set callback for camera release events"""  
        self._camera_release_callback = callback
    
    async def _check_pending_commands(self):
        """Check for pending commands from backend"""
        if not self.worker_id:
            return
        
        try:
            response = await self.http_client.get(
                f"{self.config.api_url}/v1/worker-management/commands/{self.worker_id}/pending",
                headers={"Authorization": f"Bearer {self.access_token}"},
                params={"limit": 5}
            )
            response.raise_for_status()
            
            result = response.json()
            commands = result.get("pending_commands", [])
            
            for command_data in commands:
                await self._process_command(command_data)
                
        except Exception as e:
            logger.debug(f"Error checking pending commands: {e}")
    
    async def _process_command(self, command_data: dict):
        """Process a single command"""
        command_id = command_data.get("command_id")
        command_str = command_data.get("command")
        parameters = command_data.get("parameters", {})
        
        try:
            command = WorkerCommand.from_string(command_str)
            logger.info(f"Processing command: {command.value} (ID: {command_id})")
            
            # Acknowledge command receipt
            await self._acknowledge_command(command_id)
            
            # Process the command
            result = None
            error_message = None
            
            try:
                if command == WorkerCommand.ASSIGN_CAMERA:
                    result = await self._handle_assign_camera_command(parameters)
                elif command == WorkerCommand.RELEASE_CAMERA:
                    result = await self._handle_release_camera_command(parameters)
                elif command == WorkerCommand.START_PROCESSING:
                    result = await self._handle_start_processing_command(parameters)
                elif command == WorkerCommand.STOP_PROCESSING:
                    result = await self._handle_stop_processing_command(parameters)
                elif command == WorkerCommand.START_STREAMING:
                    result = await self._handle_start_streaming_command(parameters)
                elif command == WorkerCommand.STOP_STREAMING:
                    result = await self._handle_stop_streaming_command(parameters)
                elif command == WorkerCommand.STATUS_REPORT:
                    result = await self._handle_status_report_command(parameters)
                elif command == WorkerCommand.RESTART:
                    result = await self._handle_restart_command(parameters)
                else:
                    error_message = f"Unknown command: {command.value}"
                    
            except Exception as cmd_error:
                error_message = f"Command execution error: {str(cmd_error)}"
                logger.error(f"Error executing command {command.value}: {cmd_error}")
            
            # Complete the command
            await self._complete_command(command_id, result, error_message)
            
        except ValueError as e:
            logger.error(f"Invalid command: {command_str} - {e}")
            await self._complete_command(command_id, None, str(e))
        except Exception as e:
            logger.error(f"Error processing command {command_id}: {e}")
            await self._complete_command(command_id, None, str(e))
    
    async def _acknowledge_command(self, command_id: str):
        """Acknowledge command receipt"""
        try:
            response = await self.http_client.post(
                f"{self.config.api_url}/v1/worker-management/commands/{command_id}/acknowledge",
                headers={"Authorization": f"Bearer {self.access_token}"},
                params={"worker_id": self.worker_id}
            )
            response.raise_for_status()
            logger.debug(f"Command {command_id} acknowledged")
        except Exception as e:
            logger.error(f"Failed to acknowledge command {command_id}: {e}")
    
    async def _complete_command(self, command_id: str, result: Optional[Dict[str, Any]], error_message: Optional[str]):
        """Complete command execution"""
        try:
            completion_data = {
                "worker_id": self.worker_id,
                "result": result or {},
                "error_message": error_message
            }
            
            response = await self.http_client.post(
                f"{self.config.api_url}/v1/worker-management/commands/{command_id}/complete",
                headers={"Authorization": f"Bearer {self.access_token}"},
                json=completion_data
            )
            response.raise_for_status()
            logger.debug(f"Command {command_id} completed")
        except Exception as e:
            logger.error(f"Failed to complete command {command_id}: {e}")
    
    async def _handle_assign_camera_command(self, parameters: dict) -> Dict[str, Any]:
        """Handle assign camera command"""
        camera_id = parameters.get("camera_id")
        camera_type = parameters.get("camera_type", "webcam")
        rtsp_url = parameters.get("rtsp_url")
        device_index = parameters.get("device_index")
        
        if not camera_id:
            raise ValueError("camera_id is required for camera assignment")
        
        # Update assigned camera
        self.assigned_camera_id = int(camera_id)
        self.assigned_camera_name = parameters.get("camera_name")
        
        # Call assignment callback if set (implemented by enhanced worker)
        if hasattr(self, '_camera_assignment_callback') and self._camera_assignment_callback:
            try:
                await self._camera_assignment_callback(camera_id, camera_type, rtsp_url, device_index)
                logger.info(f"Camera {camera_id} assigned via callback")
            except Exception as e:
                logger.error(f"Camera assignment callback failed: {e}")
                raise
        
        # Update status to indicate we're processing
        await self._send_heartbeat(WorkerStatus.PROCESSING)
        
        return {
            "status": "camera_assigned",
            "camera_id": camera_id,
            "camera_type": camera_type,
            "message": f"Camera {camera_id} assigned successfully"
        }
    
    async def _handle_release_camera_command(self, parameters: dict) -> Dict[str, Any]:
        """Handle release camera command"""
        camera_id = parameters.get("camera_id", self.assigned_camera_id)
        
        if not camera_id:
            logger.warning("No camera ID provided and no camera currently assigned")
            return {"status": "no_camera_to_release"}
        
        # Call release callback if set (implemented by enhanced worker)
        if hasattr(self, '_camera_release_callback') and self._camera_release_callback:
            try:
                await self._camera_release_callback(camera_id)
                logger.info(f"Camera {camera_id} released via callback")
            except Exception as e:
                logger.error(f"Camera release callback failed: {e}")
                # Continue with release even if callback fails
        
        # Clear assigned camera
        old_camera_id = self.assigned_camera_id
        self.assigned_camera_id = None
        self.assigned_camera_name = None
        
        # Update status to idle
        await self._send_heartbeat(WorkerStatus.IDLE)
        
        return {
            "status": "camera_released",
            "camera_id": old_camera_id,
            "message": f"Camera {old_camera_id} released successfully"
        }
    
    async def _handle_start_processing_command(self, parameters: dict) -> Dict[str, Any]:
        """Handle start processing command"""
        if not self.assigned_camera_id:
            raise ValueError("Cannot start processing - no camera assigned")
        
        # Update status to processing
        await self._send_heartbeat(WorkerStatus.PROCESSING)
        logger.info("Processing started")
        return {"status": "processing_started", "camera_id": self.assigned_camera_id}
    
    async def _handle_stop_processing_command(self, _parameters: dict) -> Dict[str, Any]:
        """Handle stop processing command"""
        # Update status to idle
        await self._send_heartbeat(WorkerStatus.IDLE)
        logger.info("Processing stopped")
        return {"status": "processing_stopped"}
    
    async def _handle_start_streaming_command(self, _parameters: dict) -> Dict[str, Any]:
        """Handle start streaming command"""
        if not self.assigned_camera_id:
            raise ValueError("No camera assigned for streaming")
        
        logger.info("Streaming started (placeholder - implement in main worker)")
        return {"status": "streaming_started", "camera_id": self.assigned_camera_id}
    
    async def _handle_stop_streaming_command(self, _parameters: dict) -> Dict[str, Any]:
        """Handle stop streaming command"""
        logger.info("Streaming stopped (placeholder - implement in main worker)")
        return {"status": "streaming_stopped"}
    
    async def _handle_status_report_command(self, _parameters: dict) -> Dict[str, Any]:
        """Handle status report command"""
        current_status = self._get_current_worker_status()
        
        status_info = {
            "worker_id": self.worker_id,
            "assigned_camera_id": self.assigned_camera_id,
            "assigned_camera_name": self.assigned_camera_name,
            "status": current_status.value,
            "faces_processed": self.faces_processed_since_heartbeat
        }
        
        # Include streaming information based on camera assignment and status
        if self.assigned_camera_id and current_status == WorkerStatus.PROCESSING:
            # Worker is actively processing the assigned camera
            status_info["active_camera_streams"] = [self.assigned_camera_id]
            status_info["total_active_streams"] = 1
        else:
            # Worker is not streaming or no camera assigned
            status_info["active_camera_streams"] = []
            status_info["total_active_streams"] = 0
        
        return status_info
    
    async def _handle_restart_command(self, parameters: dict) -> Dict[str, Any]:
        """Handle restart command"""
        restart_type = parameters.get("restart_type", "graceful")
        logger.warning(f"Restart command received: {restart_type}")
        
        # This would trigger the main worker restart logic
        self.shutdown_requested = True
        
        return {
            "status": "restart_initiated",
            "restart_type": restart_type,
            "message": "Worker restart initiated"
        }