from __future__ import annotations

import asyncio
import json
import logging
import socket
import time
from datetime import datetime, timezone
from typing import Dict, Optional, Any

import httpx
from pydantic import BaseModel

from common.enums.worker import WorkerStatus
from common.enums.commands import WorkerCommand

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
            "camera_source": "rtsp" if config.rtsp_url else "usb"
        }
    
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
        
        # Register with backend
        await self._register_worker()
        
        # Start heartbeat task
        if self.worker_id:
            self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            logger.info(f"Worker client initialized with ID: {self.worker_id}")
        else:
            logger.error("Failed to register worker, heartbeat not started")
    
    async def shutdown(self):
        """Cleanup worker client"""
        # Cancel heartbeat task
        if self.heartbeat_task and not self.heartbeat_task.done():
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass
        
        # Send final offline status
        if self.worker_id:
            try:
                await self._send_heartbeat(status=WorkerStatus.OFFLINE)
                logger.info("Sent offline status to backend")
            except Exception as e:
                logger.warning(f"Failed to send offline status: {e}")
        
        # Close HTTP client
        if self.http_client:
            await self.http_client.aclose()
        
        logger.info("Worker client shutdown complete")
    
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
        """Register worker with backend"""
        for attempt in range(self.max_registration_retries):
            try:
                # Authenticate first
                if not await self._authenticate():
                    continue
                
                registration_data = {
                    "worker_name": self.worker_name,
                    "hostname": self.hostname,
                    "worker_version": self.worker_version,
                    "capabilities": self.capabilities,
                    "site_id": self._parse_site_id(),
                    # camera_id is removed - backend will auto-assign
                }
                
                response = await self.http_client.post(
                    f"{self.config.api_url}/v1/registry/workers/register",
                    json=registration_data,
                    headers={"Authorization": f"Bearer {self.access_token}"}
                )
                response.raise_for_status()
                
                result = response.json()
                self.worker_id = result["worker_id"]
                
                # Capture camera assignment
                if "assigned_camera_id" in result and result["assigned_camera_id"]:
                    self.assigned_camera_id = int(result["assigned_camera_id"])
                    logger.info(f"Worker registered and assigned camera {self.assigned_camera_id}")
                else:
                    logger.info(f"Worker registered but no camera assigned")
                
                logger.info(f"Worker registered successfully: {result['message']}")
                return
                
            except Exception as e:
                logger.error(f"Worker registration failed (attempt {attempt + 1}/{self.max_registration_retries}): {e}")
                
                if attempt < self.max_registration_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    await asyncio.sleep(wait_time)
        
        logger.error("Failed to register worker after all attempts")
    
    async def _send_heartbeat(self, status: WorkerStatus = WorkerStatus.IDLE, error_message: Optional[str] = None):
        """Send heartbeat to backend and check for shutdown signals"""
        if not self.worker_id:
            logger.warning("Cannot send heartbeat - worker not registered")
            return
        
        try:
            await self._ensure_authenticated()
            
            # First check for shutdown signals and commands
            await self._check_shutdown_signal()
            await self._check_pending_commands()
            
            heartbeat_data = {
                "status": status.value,
                "faces_processed_count": self.faces_processed_since_heartbeat,
                "capabilities": self.capabilities
            }
            
            # Include current camera if processing
            if status == WorkerStatus.PROCESSING and self.assigned_camera_id:
                heartbeat_data["current_camera_id"] = self.assigned_camera_id
            
            if error_message:
                heartbeat_data["error_message"] = error_message
            
            response = await self.http_client.post(
                f"{self.config.api_url}/v1/registry/workers/{self.worker_id}/heartbeat",
                json=heartbeat_data,
                headers={"Authorization": f"Bearer {self.access_token}"}
            )
            response.raise_for_status()
            
            # Handle response from heartbeat
            result = response.json()
            if "assigned_camera_id" in result and result["assigned_camera_id"]:
                new_camera_id = int(result["assigned_camera_id"])
                if new_camera_id != self.assigned_camera_id:
                    self.assigned_camera_id = new_camera_id
                    logger.info(f"Camera assignment updated to: {self.assigned_camera_id}")
            elif result.get("assigned_camera_id") is None:
                if self.assigned_camera_id is not None:
                    logger.info(f"Camera assignment removed (was {self.assigned_camera_id})")
                    self.assigned_camera_id = None
            
            # Reset counter after successful heartbeat
            self.faces_processed_since_heartbeat = 0
            logger.debug(f"Heartbeat sent successfully - status: {status}, camera: {self.assigned_camera_id}")
            
        except Exception as e:
            logger.error(f"Failed to send heartbeat: {e}")
    
    async def _heartbeat_loop(self):
        """Main heartbeat loop"""
        heartbeat_interval = 30  # 30 seconds
        
        while True:
            try:
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
        """Request camera assignment from backend"""
        if not self.worker_id:
            logger.warning("Cannot request camera assignment - worker not registered")
            return None
        
        try:
            await self._ensure_authenticated()
            
            response = await self.http_client.post(
                f"{self.config.api_url}/v1/workers/{self.worker_id}/request-camera",
                headers={"Authorization": f"Bearer {self.access_token}"}
            )
            response.raise_for_status()
            
            result = response.json()
            if result.get("assigned_camera_id"):
                self.assigned_camera_id = int(result["assigned_camera_id"])
                self.assigned_camera_name = result.get("assigned_camera_name")
                logger.info(f"Camera assignment requested successfully: {self.assigned_camera_id} ({self.assigned_camera_name})")
                return self.assigned_camera_id
            else:
                logger.info("Camera assignment requested but no cameras available")
                return None
                
        except Exception as e:
            logger.error(f"Failed to request camera assignment: {e}")
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
            response = await self.http_client.post(
                f"{self.config.api_url}/v1/worker-management/commands/{command_id}/complete",
                headers={"Authorization": f"Bearer {self.access_token}"},
                json={
                    "worker_id": self.worker_id,
                    "result": result,
                    "error_message": error_message
                }
            )
            response.raise_for_status()
            logger.debug(f"Command {command_id} completed")
        except Exception as e:
            logger.error(f"Failed to complete command {command_id}: {e}")
    
    async def _handle_assign_camera_command(self, parameters: dict) -> Dict[str, Any]:
        """Handle camera assignment command"""
        camera_id = parameters.get("camera_id")
        camera_name = parameters.get("camera_name")
        rtsp_url = parameters.get("rtsp_url")
        device_index = parameters.get("device_index")
        camera_type = parameters.get("camera_type", "webcam")
        
        if not camera_id:
            raise ValueError("camera_id is required for camera assignment")
        
        # Update camera configuration
        self.assigned_camera_id = int(camera_id)
        self.assigned_camera_name = camera_name
        self.camera_config = {
            "camera_id": camera_id,
            "camera_name": camera_name,
            "rtsp_url": rtsp_url,
            "device_index": device_index,
            "camera_type": camera_type
        }
        
        # If we have a callback to the main worker, notify it of camera assignment
        if hasattr(self, '_camera_assignment_callback') and self._camera_assignment_callback:
            try:
                success = await self._camera_assignment_callback(camera_id, self.camera_config)
                if success:
                    logger.info(f"Camera assigned and streaming started: {camera_id} ({camera_name})")
                    return {"camera_id": camera_id, "camera_name": camera_name, "streaming": True}
                else:
                    logger.error(f"Failed to start streaming for assigned camera: {camera_id}")
                    return {"camera_id": camera_id, "camera_name": camera_name, "streaming": False}
            except Exception as e:
                logger.error(f"Error in camera assignment callback: {e}")
                return {"camera_id": camera_id, "camera_name": camera_name, "error": str(e)}
        
        logger.info(f"Camera assigned: {camera_id} ({camera_name})")
        return {"camera_id": camera_id, "camera_name": camera_name}
    
    async def _handle_release_camera_command(self, _parameters: dict) -> Dict[str, Any]:
        """Handle camera release command"""
        old_camera_id = self.assigned_camera_id
        old_camera_name = self.assigned_camera_name
        
        # If we have a callback to the main worker, notify it of camera release
        if hasattr(self, '_camera_release_callback') and self._camera_release_callback and old_camera_id:
            try:
                success = await self._camera_release_callback(str(old_camera_id))
                if success:
                    logger.info(f"Camera released and streaming stopped: {old_camera_id} ({old_camera_name})")
                else:
                    logger.warning(f"Issues releasing camera: {old_camera_id}")
            except Exception as e:
                logger.error(f"Error in camera release callback: {e}")
        
        # Clear camera configuration
        self.assigned_camera_id = None
        self.assigned_camera_name = None
        self.camera_config = None
        
        logger.info(f"Camera released: {old_camera_id} ({old_camera_name})")
        return {"released_camera_id": old_camera_id, "released_camera_name": old_camera_name}
    
    async def _handle_start_processing_command(self, _parameters: dict) -> Dict[str, Any]:
        """Handle start processing command"""
        if not self.assigned_camera_id:
            raise ValueError("No camera assigned for processing")
        
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
        return {
            "worker_id": self.worker_id,
            "assigned_camera_id": self.assigned_camera_id,
            "assigned_camera_name": self.assigned_camera_name,
            "status": "idle",  # This would be dynamic in real implementation
            "faces_processed": self.faces_processed_since_heartbeat
        }
    
    async def _handle_restart_command(self, _parameters: dict) -> Dict[str, Any]:
        """Handle restart command"""
        logger.warning("Restart command received - setting restart flag")
        # This would be implemented in the main worker loop
        return {"status": "restart_requested"}