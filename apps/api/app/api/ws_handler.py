"""
WebSocket Handler for Worker Communication
Implements the GPT plan's message handling with intent tracking
"""
import asyncio
import json
import logging
from typing import Dict, Any, Optional, Set
from uuid import uuid4
from datetime import datetime, timedelta

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from .ws_protocol import (
    parse_message, serialize_message, MessageType, IntentStatus,
    RegisterMessage, HeartbeatMessage, AckMessage, EventMessage,
    create_start_message, create_stop_message, create_drain_message,
    CameraSource, SourceType
)
from ..core.correlation import get_structured_logger, set_correlation_id, get_or_create_correlation_id
from ..services.assignment_service import assignment_service
from ..services.worker_registry import worker_registry, WorkerStatus
from ..core.database import get_db

logger = get_structured_logger(__name__)


class IntentTracker:
    """Track pending intents with timeout and correlation"""
    
    def __init__(self):
        self.pending_intents: Dict[str, Dict[str, Any]] = {}
        self.cleanup_task: Optional[asyncio.Task] = None
        self.intent_timeout = timedelta(minutes=2)  # 2min timeout for intents
    
    def add_intent(
        self, 
        intent_id: str, 
        worker_id: str, 
        message_type: MessageType,
        correlation_id: str,
        payload: Optional[Dict[str, Any]] = None
    ):
        """Add a pending intent"""
        self.pending_intents[intent_id] = {
            "worker_id": worker_id,
            "message_type": message_type,
            "correlation_id": correlation_id,
            "payload": payload or {},
            "created_at": datetime.utcnow(),
            "status": "pending"
        }
        
        logger.info(
            "intent_created",
            intent_id=intent_id,
            worker_id=worker_id,
            message_type=message_type,
            correlation_id=correlation_id
        )
    
    def handle_ack(self, intent_id: str, status: IntentStatus, details: Optional[str] = None) -> bool:
        """Handle ACK for intent"""
        if intent_id not in self.pending_intents:
            logger.warning("ack_for_unknown_intent", intent_id=intent_id)
            return False
        
        intent = self.pending_intents[intent_id]
        intent["status"] = status.value
        intent["ack_at"] = datetime.utcnow()
        intent["details"] = details
        
        logger.info(
            "intent_acked",
            intent_id=intent_id,
            status=status.value,
            worker_id=intent["worker_id"],
            correlation_id=intent["correlation_id"],
            details=details
        )
        
        # Remove completed intents
        if status in [IntentStatus.SUCCESS, IntentStatus.ERROR]:
            del self.pending_intents[intent_id]
        
        return True
    
    def cleanup_expired_intents(self):
        """Remove expired intents"""
        now = datetime.utcnow()
        expired = []
        
        for intent_id, intent in self.pending_intents.items():
            if now - intent["created_at"] > self.intent_timeout:
                expired.append(intent_id)
        
        for intent_id in expired:
            intent = self.pending_intents.pop(intent_id)
            logger.warning(
                "intent_expired",
                intent_id=intent_id,
                worker_id=intent["worker_id"],
                message_type=intent["message_type"],
                correlation_id=intent["correlation_id"]
            )


class WorkerWebSocketHandler:
    """
    WebSocket handler for worker communication
    Implements GPT plan's message protocol with intent tracking
    """
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.worker_connections: Dict[str, str] = {}  # worker_id -> connection_id
        self.intent_tracker = IntentTracker()
    
    async def handle_connection(self, websocket: WebSocket, worker_id: str):
        """Handle new worker WebSocket connection"""
        await websocket.accept()
        
        connection_id = str(uuid4())
        self.active_connections[connection_id] = websocket
        self.worker_connections[worker_id] = connection_id
        
        correlation_id = get_or_create_correlation_id()
        
        logger.info(
            "worker_connected",
            worker_id=worker_id,
            connection_id=connection_id,
            correlation_id=correlation_id
        )
        
        try:
            await self._handle_messages(websocket, worker_id, connection_id)
        except WebSocketDisconnect:
            logger.info(
                "worker_disconnected",
                worker_id=worker_id,
                connection_id=connection_id,
                correlation_id=correlation_id
            )
        except Exception as e:
            logger.error(
                "websocket_error",
                worker_id=worker_id,
                error=str(e),
                correlation_id=correlation_id
            )
        finally:
            await self._cleanup_connection(worker_id, connection_id)
    
    async def _handle_messages(self, websocket: WebSocket, worker_id: str, connection_id: str):
        """Handle incoming messages from worker"""
        while True:
            try:
                # Receive message
                data = await websocket.receive_text()
                message_dict = json.loads(data)
                
                # Set correlation ID from message
                correlation_id = message_dict.get("correlation_id", get_or_create_correlation_id())
                set_correlation_id(correlation_id)
                
                # Parse message using Pydantic schemas
                message = parse_message(message_dict)
                
                logger.info(
                    "message_received",
                    worker_id=worker_id,
                    message_type=message.type,
                    correlation_id=correlation_id
                )
                
                # Route message to appropriate handler
                await self._route_message(websocket, worker_id, message)
                
            except json.JSONDecodeError as e:
                logger.error(
                    "invalid_json",
                    worker_id=worker_id,
                    error=str(e)
                )
                await self._send_error(websocket, "Invalid JSON format")
            
            except Exception as e:
                logger.error(
                    "message_handling_error",
                    worker_id=worker_id,
                    error=str(e)
                )
                await self._send_error(websocket, f"Message handling error: {str(e)}")
    
    async def _route_message(self, websocket: WebSocket, worker_id: str, message):
        """Route message to appropriate handler based on type"""
        
        if message.type == MessageType.REGISTER:
            await self._handle_register(websocket, worker_id, message)
        
        elif message.type == MessageType.HEARTBEAT:
            await self._handle_heartbeat(websocket, worker_id, message)
        
        elif message.type == MessageType.ACK:
            await self._handle_ack(websocket, worker_id, message)
        
        elif message.type == MessageType.EVENT:
            await self._handle_event(websocket, worker_id, message)
        
        else:
            logger.warning(
                "unknown_message_type",
                worker_id=worker_id,
                message_type=message.type,
                correlation_id=getattr(message, 'correlation_id', None)
            )
    
    async def _handle_register(self, websocket: WebSocket, worker_id: str, message: RegisterMessage):
        """Handle REGISTER message"""
        correlation_id = message.correlation_id or get_or_create_correlation_id()
        
        try:
            # Register worker in worker registry
            worker_info = await worker_registry.register_worker(
                worker_id=worker_id,
                tenant_id=message.labels.get("tenant_id") if message.labels else None,
                hostname=message.labels.get("hostname", "unknown") if message.labels else "unknown",
                ip_address=message.labels.get("ip_address") if message.labels else None,
                worker_name=message.labels.get("worker_name", worker_id) if message.labels else worker_id,
                worker_version=message.version,
                capabilities=json.dumps(message.capacity) if message.capacity else None,
                site_id=message.site_id
            )
            
            logger.info(
                "worker_registered",
                worker_id=worker_id,
                site_id=message.site_id,
                version=message.version,
                correlation_id=correlation_id
            )
            
            # Try to assign camera if available
            async with get_db() as db:
                camera = await assignment_service.assign_camera_with_lease(
                    db=db,
                    tenant_id=worker_info.tenant_id,
                    worker_id=worker_id,
                    site_id=message.site_id
                )
                
                if camera:
                    logger.info(
                        "auto_assignment_success",
                        worker_id=worker_id,
                        camera_id=camera.camera_id,
                        correlation_id=correlation_id
                    )
        
        except Exception as e:
            logger.error(
                "registration_error",
                worker_id=worker_id,
                error=str(e),
                correlation_id=correlation_id
            )
            await self._send_error(websocket, f"Registration failed: {str(e)}")
    
    async def _handle_heartbeat(self, websocket: WebSocket, worker_id: str, message: HeartbeatMessage):
        """Handle HEARTBEAT message with lease renewals"""
        correlation_id = message.correlation_id or get_or_create_correlation_id()
        
        try:
            # Update worker heartbeat
            await worker_registry.update_worker_heartbeat(
                worker_id=worker_id,
                metrics={
                    "cpu_usage": message.metrics.cpu_usage,
                    "memory_usage": message.metrics.memory_usage,
                    "active_cameras": message.metrics.active_cameras,
                    "frames_processed": message.metrics.frames_processed,
                    "errors_count": message.metrics.errors_count
                }
            )
            
            # Process lease renewals
            if message.renew:
                async with get_db() as db:
                    renewal_requests = [
                        {"camera_id": r.camera_id, "generation": r.generation}
                        for r in message.renew
                    ]
                    
                    result = await assignment_service.renew_lease(
                        db=db,
                        worker_id=worker_id,
                        renewals=renewal_requests
                    )
                    
                    logger.debug(
                        "lease_renewals_processed",
                        worker_id=worker_id,
                        renewal_count=len(message.renew),
                        result=result,
                        correlation_id=correlation_id
                    )
            
            logger.debug(
                "heartbeat_processed",
                worker_id=worker_id,
                correlation_id=correlation_id
            )
        
        except Exception as e:
            logger.error(
                "heartbeat_error",
                worker_id=worker_id,
                error=str(e),
                correlation_id=correlation_id
            )
    
    async def _handle_ack(self, websocket: WebSocket, worker_id: str, message: AckMessage):
        """Handle ACK message for intent tracking"""
        correlation_id = message.correlation_id or get_or_create_correlation_id()
        
        success = self.intent_tracker.handle_ack(
            intent_id=message.intent_id,
            status=message.status,
            details=message.details
        )
        
        if not success:
            logger.warning(
                "ack_processing_failed",
                intent_id=message.intent_id,
                worker_id=worker_id,
                correlation_id=correlation_id
            )
    
    async def _handle_event(self, websocket: WebSocket, worker_id: str, message: EventMessage):
        """Handle EVENT message from worker"""
        correlation_id = message.correlation_id or get_or_create_correlation_id()
        
        logger.info(
            "worker_event_received",
            worker_id=worker_id,
            camera_id=message.camera_id,
            event_type=message.event_type,
            generation=message.generation,
            seq=message.seq,
            correlation_id=correlation_id
        )
        
        # TODO: Route events to appropriate handlers based on event_type
        # e.g., pipeline_ready, pipeline_error, rtsp_error, etc.
    
    async def send_start_command(
        self,
        worker_id: str,
        camera_id: int,
        generation: int,
        rtsp_url: Optional[str] = None,
        device_index: Optional[int] = None,
        correlation_id: Optional[str] = None
    ) -> Optional[str]:
        """Send START command to worker"""
        if worker_id not in self.worker_connections:
            logger.error("worker_not_connected", worker_id=worker_id)
            return None
        
        connection_id = self.worker_connections[worker_id]
        websocket = self.active_connections.get(connection_id)
        
        if not websocket:
            logger.error("websocket_not_found", worker_id=worker_id)
            return None
        
        intent_id = str(uuid4())
        correlation_id = correlation_id or get_or_create_correlation_id()
        
        # Determine source type and config
        if rtsp_url:
            source = CameraSource(type=SourceType.RTSP, rtsp_url=rtsp_url)
        else:
            source = CameraSource(type=SourceType.WEBCAM, device_index=device_index or 0)
        
        # Create START message
        message = create_start_message(
            intent_id=intent_id,
            camera_id=camera_id,
            generation=generation,
            source=source,
            correlation_id=correlation_id
        )
        
        # Track intent
        self.intent_tracker.add_intent(
            intent_id=intent_id,
            worker_id=worker_id,
            message_type=MessageType.START,
            correlation_id=correlation_id,
            payload={"camera_id": camera_id, "generation": generation}
        )
        
        # Send message
        try:
            await websocket.send_text(json.dumps(serialize_message(message)))
            
            logger.info(
                "start_command_sent",
                worker_id=worker_id,
                intent_id=intent_id,
                camera_id=camera_id,
                generation=generation,
                correlation_id=correlation_id
            )
            
            return intent_id
        
        except Exception as e:
            logger.error(
                "start_command_failed",
                worker_id=worker_id,
                intent_id=intent_id,
                error=str(e),
                correlation_id=correlation_id
            )
            return None
    
    async def _send_error(self, websocket: WebSocket, error_message: str):
        """Send error message to worker"""
        try:
            error_data = {
                "type": "ERROR",
                "message": error_message,
                "timestamp": datetime.utcnow().isoformat()
            }
            await websocket.send_text(json.dumps(error_data))
        except Exception as e:
            logger.error("failed_to_send_error", error=str(e))
    
    async def _cleanup_connection(self, worker_id: str, connection_id: str):
        """Clean up connection resources"""
        try:
            # Remove from active connections
            self.active_connections.pop(connection_id, None)
            
            # Remove worker connection mapping
            if self.worker_connections.get(worker_id) == connection_id:
                del self.worker_connections[worker_id]
            
            # Update worker status in registry
            worker = worker_registry.get_worker(worker_id)
            if worker:
                worker.status = WorkerStatus.OFFLINE
            
            logger.info(
                "connection_cleaned_up",
                worker_id=worker_id,
                connection_id=connection_id
            )
        
        except Exception as e:
            logger.error(
                "cleanup_error",
                worker_id=worker_id,
                connection_id=connection_id,
                error=str(e)
            )


# Global instance
ws_handler = WorkerWebSocketHandler()