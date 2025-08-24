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
                await self._send_heartbeat(status="offline")
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
                    "site_id": int(self.config.site_id) if self.config.site_id and self.config.site_id.isdigit() else None,
                    # camera_id is removed - backend will auto-assign
                }
                
                response = await self.http_client.post(
                    f"{self.config.api_url}/v1/workers/register",
                    json=registration_data,
                    headers={"Authorization": f"Bearer {self.access_token}"}
                )
                response.raise_for_status()
                
                result = response.json()
                self.worker_id = result["worker_id"]
                
                # Capture camera assignment
                if "assigned_camera_id" in result:
                    self.assigned_camera_id = int(result["assigned_camera_id"])
                    self.assigned_camera_name = result.get("assigned_camera_name")
                    logger.info(f"Worker registered and assigned camera {self.assigned_camera_id} ({self.assigned_camera_name})")
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
    
    async def _send_heartbeat(self, status: str = "idle", error_message: Optional[str] = None):
        """Send heartbeat to backend"""
        if not self.worker_id:
            logger.warning("Cannot send heartbeat - worker not registered")
            return
        
        try:
            await self._ensure_authenticated()
            
            heartbeat_data = {
                "status": status,
                "faces_processed_count": self.faces_processed_since_heartbeat,
                "capabilities": self.capabilities
            }
            
            # Include current camera if processing
            if status == "processing" and self.assigned_camera_id:
                heartbeat_data["current_camera_id"] = self.assigned_camera_id
            
            if error_message:
                heartbeat_data["error_message"] = error_message
            
            response = await self.http_client.post(
                f"{self.config.api_url}/v1/workers/{self.worker_id}/heartbeat",
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
        await self._send_heartbeat(status="error", error_message=error_message)
    
    async def report_maintenance(self):
        """Report maintenance status to backend"""
        await self._send_heartbeat(status="maintenance")
    
    async def report_processing(self):
        """Report that worker is currently processing faces"""
        await self._send_heartbeat(status="processing")
    
    async def report_idle(self):
        """Report that worker is idle and ready for work"""
        await self._send_heartbeat(status="idle")
    
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