"""
WebRTC Signaling Server for P2P Camera Streaming

This module handles WebRTC signaling between frontend clients and workers
for peer-to-peer camera streaming, eliminating the need for HTTP streaming
through the API server.

Architecture:
- API acts as WebRTC signaling server only (no media relay)
- Workers act as WebRTC peers offering camera streams
- Frontend clients connect directly to workers via WebRTC
- Signaling messages: offers, answers, ICE candidates

Benefits:
- Direct P2P streaming (no server bandwidth usage)
- Lower latency than HTTP streaming
- Scalable (API only handles signaling, not media)
- No port conflicts (workers use dynamic ICE ports)
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from common.enums.worker import WorkerStatus
from fastapi import (APIRouter, Depends, HTTPException, WebSocket,
                     WebSocketDisconnect)
from pydantic import BaseModel, Field

from ..core.security import get_current_user, verify_jwt
from ..services.worker_registry import worker_registry

logger = logging.getLogger(__name__)


# Pydantic Models
class UserInfo(BaseModel):
    sub: str
    role: str
    tenant_id: str


class WebRTCSignalingMessage(BaseModel):
    type: str = Field(
        ...,
        description="Message type: offer, answer, ice-candidate, stream-request, stream-stop",
    )
    session_id: str = Field(..., description="Unique session identifier")
    from_id: str = Field(..., description="Sender identifier (worker_id or client_id)")
    to_id: str = Field(..., description="Target identifier (worker_id or client_id)")
    camera_id: Optional[int] = Field(None, description="Camera ID for stream requests")
    site_id: Optional[int] = Field(None, description="Site ID for stream requests")
    sdp: Optional[str] = Field(None, description="SDP offer/answer for WebRTC")
    ice_candidate: Optional[Dict[str, Any]] = Field(
        None, description="ICE candidate data"
    )
    timestamp: Optional[str] = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class StreamRequestMessage(BaseModel):
    session_id: str
    camera_id: int
    site_id: int
    client_id: str


class StreamStopMessage(BaseModel):
    session_id: str
    camera_id: int
    client_id: str


# WebRTC Session Management
class WebRTCSession:
    def __init__(
        self,
        session_id: str,
        client_id: str,
        worker_id: str,
        camera_id: int,
        site_id: int,
    ):
        self.session_id = session_id
        self.client_id = client_id
        self.worker_id = worker_id
        self.camera_id = camera_id
        self.site_id = site_id
        self.created_at = datetime.now(timezone.utc)
        self.status = "initiated"  # initiated, connecting, connected, disconnected
        self.offer_received = False
        self.answer_received = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "client_id": self.client_id,
            "worker_id": self.worker_id,
            "camera_id": self.camera_id,
            "site_id": self.site_id,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "offer_received": self.offer_received,
            "answer_received": self.answer_received,
        }


class WebRTCSignalingManager:
    """Manages WebRTC signaling sessions and WebSocket connections"""

    def __init__(self):
        # WebSocket connections: {connection_id: websocket}
        self.client_connections: Dict[str, WebSocket] = {}
        self.worker_connections: Dict[str, WebSocket] = {}

        # Active sessions: {session_id: WebRTCSession}
        self.active_sessions: Dict[str, WebRTCSession] = {}

        # Client/Worker mappings
        self.client_to_session: Dict[str, Set[str]] = {}  # {client_id: {session_ids}}
        self.worker_to_session: Dict[str, Set[str]] = {}  # {worker_id: {session_ids}}

    async def connect_client(
        self, client_id: str, websocket: WebSocket, tenant_id: str
    ):
        """Register client WebSocket connection"""
        await websocket.accept()
        self.client_connections[client_id] = websocket
        logger.info(f"Client {client_id} connected for tenant {tenant_id}")

        # Send connection confirmation
        await websocket.send_json(
            {
                "type": "connected",
                "client_id": client_id,
                "role": "client",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    async def connect_worker(
        self, worker_id: str, websocket: WebSocket, tenant_id: str
    ):
        """Register worker WebSocket connection"""
        await websocket.accept()
        self.worker_connections[worker_id] = websocket
        logger.info(
            f"Worker {worker_id} connected for WebRTC signaling in tenant {tenant_id}"
        )

        # Send connection confirmation
        await websocket.send_json(
            {
                "type": "connected",
                "worker_id": worker_id,
                "role": "worker",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    def disconnect_client(self, client_id: str):
        """Remove client connection and cleanup sessions"""
        if client_id in self.client_connections:
            del self.client_connections[client_id]

        # Cleanup client sessions
        if client_id in self.client_to_session:
            session_ids = self.client_to_session[client_id].copy()
            for session_id in session_ids:
                asyncio.create_task(self._cleanup_session(session_id))
            del self.client_to_session[client_id]

        logger.info(f"Client {client_id} disconnected and sessions cleaned up")

    def disconnect_worker(self, worker_id: str):
        """Remove worker connection and cleanup sessions"""
        if worker_id in self.worker_connections:
            del self.worker_connections[worker_id]

        # Cleanup worker sessions
        if worker_id in self.worker_to_session:
            session_ids = self.worker_to_session[worker_id].copy()
            for session_id in session_ids:
                asyncio.create_task(self._cleanup_session(session_id))
            del self.worker_to_session[worker_id]

        logger.info(f"Worker {worker_id} disconnected and sessions cleaned up")

    async def create_streaming_session(
        self, client_id: str, camera_id: int, site_id: int, tenant_id: str
    ) -> str:
        """Create new WebRTC streaming session"""

        # Find available worker for the camera
        worker = self._find_worker_for_camera(camera_id, site_id, tenant_id)
        if not worker:
            raise HTTPException(
                status_code=404, detail="No worker available for camera"
            )

        # Generate session ID
        session_id = str(uuid.uuid4())

        # Create session
        session = WebRTCSession(
            session_id=session_id,
            client_id=client_id,
            worker_id=worker.worker_id,
            camera_id=camera_id,
            site_id=site_id,
        )

        self.active_sessions[session_id] = session

        # Update mappings
        if client_id not in self.client_to_session:
            self.client_to_session[client_id] = set()
        self.client_to_session[client_id].add(session_id)

        if worker.worker_id not in self.worker_to_session:
            self.worker_to_session[worker.worker_id] = set()
        self.worker_to_session[worker.worker_id].add(session_id)

        logger.info(
            f"Created WebRTC session {session_id}: client {client_id} -> worker {worker.worker_id} for camera {camera_id}"
        )

        # Notify worker about new streaming session
        await self._send_to_worker(
            worker.worker_id,
            {
                "type": "stream-request",
                "session_id": session_id,
                "client_id": client_id,
                "camera_id": camera_id,
                "site_id": site_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

        return session_id

    async def handle_signaling_message(self, message: WebRTCSignalingMessage) -> bool:
        """Route signaling message between client and worker"""

        session = self.active_sessions.get(message.session_id)
        if not session:
            logger.warning(f"Received message for unknown session {message.session_id}")
            return False

        # Route message based on sender
        if message.from_id == session.client_id:
            # Message from client to worker
            await self._send_to_worker(session.worker_id, message.dict())

            # Update session state
            if message.type == "answer":
                session.answer_received = True
                session.status = "connecting"
            elif message.type == "ice-candidate":
                if session.offer_received and session.answer_received:
                    session.status = "connecting"

        elif message.from_id == session.worker_id:
            # Message from worker to client
            await self._send_to_client(session.client_id, message.dict())

            # Update session state
            if message.type == "offer":
                session.offer_received = True
                session.status = "connecting"
            elif message.type == "ice-candidate":
                if session.offer_received and session.answer_received:
                    session.status = "connecting"

        else:
            logger.warning(
                f"Invalid sender {message.from_id} for session {message.session_id}"
            )
            return False

        return True

    async def stop_streaming_session(self, session_id: str) -> bool:
        """Stop WebRTC streaming session"""

        session = self.active_sessions.get(session_id)
        if not session:
            return False

        # Notify both client and worker
        stop_message = {
            "type": "stream-stop",
            "session_id": session_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        await self._send_to_client(session.client_id, stop_message)
        await self._send_to_worker(session.worker_id, stop_message)

        # Cleanup session
        await self._cleanup_session(session_id)

        return True

    async def _cleanup_session(self, session_id: str):
        """Clean up session and mappings"""

        session = self.active_sessions.get(session_id)
        if not session:
            return

        # Remove from mappings
        if session.client_id in self.client_to_session:
            self.client_to_session[session.client_id].discard(session_id)
            if not self.client_to_session[session.client_id]:
                del self.client_to_session[session.client_id]

        if session.worker_id in self.worker_to_session:
            self.worker_to_session[session.worker_id].discard(session_id)
            if not self.worker_to_session[session.worker_id]:
                del self.worker_to_session[session.worker_id]

        # Remove session
        del self.active_sessions[session_id]

        logger.info(f"Cleaned up WebRTC session {session_id}")

    async def _send_to_client(self, client_id: str, message: Dict[str, Any]):
        """Send message to client WebSocket"""

        websocket = self.client_connections.get(client_id)
        if not websocket:
            logger.warning(f"Client {client_id} not connected for message delivery")
            return

        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Failed to send message to client {client_id}: {e}")
            # Remove disconnected client
            self.disconnect_client(client_id)

    async def _send_to_worker(self, worker_id: str, message: Dict[str, Any]):
        """Send message to worker WebSocket"""

        websocket = self.worker_connections.get(worker_id)
        if not websocket:
            logger.warning(f"Worker {worker_id} not connected for message delivery")
            return

        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Failed to send message to worker {worker_id}: {e}")
            # Remove disconnected worker
            self.disconnect_worker(worker_id)

    def _find_worker_for_camera(self, camera_id: int, site_id: int, tenant_id: str):
        """Find available worker that can handle the camera"""

        # Get all workers for debugging
        all_workers = worker_registry.list_workers(
            tenant_id=tenant_id, include_offline=True
        )

        logger.info(
            f"Looking for worker for camera {camera_id} at site {site_id} (tenant {tenant_id})"
        )
        logger.info(f"Total workers in tenant: {len(all_workers)}")

        for worker in all_workers:
            logger.info(
                f"Worker {worker.worker_id}: site={worker.site_id}, status={worker.status}, capabilities={worker.capabilities}"
            )

        # Get workers for the tenant and site - try all statuses first
        workers = worker_registry.list_workers(
            tenant_id=tenant_id,
            site_id=site_id,
            status=None,  # Try any status first
            include_offline=False,
        )

        logger.info(f"Workers at site {site_id}: {len(workers)}")

        # Filter workers with WebRTC capability
        capable_workers = [
            w
            for w in workers
            if w.capabilities and w.capabilities.get("webrtc_streaming", False)
        ]

        logger.info(f"WebRTC-capable workers: {len(capable_workers)}")

        if not capable_workers:
            # Try again with any worker that has webrtc capability regardless of status
            all_capable_workers = [
                w
                for w in all_workers
                if w.capabilities and w.capabilities.get("webrtc_streaming", False)
            ]
            logger.warning(
                f"No WebRTC-capable workers found for camera {camera_id} at site {site_id}"
            )
            logger.warning(
                f"All WebRTC-capable workers in tenant: {len(all_capable_workers)}"
            )
            return None

        # For now, return first available worker (prefer IDLE, but allow others)
        idle_workers = [
            w for w in capable_workers if w.status == WorkerStatus.IDLE.value
        ]
        if idle_workers:
            logger.info(
                f"Selected idle worker {idle_workers[0].worker_id} for WebRTC streaming"
            )
            return idle_workers[0]
        else:
            logger.info(
                f"No idle workers, selecting first available: {capable_workers[0].worker_id}"
            )
            return capable_workers[0]

    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session information"""
        session = self.active_sessions.get(session_id)
        return session.to_dict() if session else None

    def list_active_sessions(self, tenant_id: str = None) -> List[Dict[str, Any]]:
        """List all active sessions, optionally filtered by tenant"""
        sessions = []

        for session in self.active_sessions.values():
            # For now, we don't filter by tenant at session level
            # since tenant info is not stored in session
            sessions.append(session.to_dict())

        return sessions


# Global signaling manager instance
signaling_manager = WebRTCSignalingManager()

# Router setup
router = APIRouter(prefix="/v1/webrtc", tags=["webrtc-signaling"])


@router.post("/sessions/start")
async def start_webrtc_session(
    request: StreamRequestMessage,
    current_user_dict: dict = Depends(get_current_user),
):
    """Start new WebRTC streaming session"""

    current_user = UserInfo(**current_user_dict)

    try:
        session_id = await signaling_manager.create_streaming_session(
            client_id=request.client_id,
            camera_id=request.camera_id,
            site_id=request.site_id,
            tenant_id=current_user.tenant_id,
        )

        return {
            "session_id": session_id,
            "status": "session_created",
            "message": "WebRTC session initiated, connect to WebSocket for signaling",
            "client_id": request.client_id,
            "camera_id": request.camera_id,
            "site_id": request.site_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start WebRTC session: {e}")
        raise HTTPException(status_code=500, detail="Failed to start WebRTC session")


@router.post("/sessions/{session_id}/stop")
async def stop_webrtc_session(
    session_id: str,
    current_user_dict: dict = Depends(get_current_user),
):
    """Stop WebRTC streaming session"""

    UserInfo(**current_user_dict)

    success = await signaling_manager.stop_streaming_session(session_id)

    if not success:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": session_id,
        "status": "session_stopped",
        "message": "WebRTC session stopped and cleaned up",
    }


@router.get("/sessions/{session_id}")
async def get_session_info(
    session_id: str,
    current_user_dict: dict = Depends(get_current_user),
):
    """Get WebRTC session information"""

    UserInfo(**current_user_dict)

    session_info = signaling_manager.get_session_info(session_id)

    if not session_info:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session": session_info,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/sessions")
async def list_sessions(
    current_user_dict: dict = Depends(get_current_user),
):
    """List active WebRTC sessions"""

    current_user = UserInfo(**current_user_dict)

    sessions = signaling_manager.list_active_sessions(tenant_id=current_user.tenant_id)

    return {
        "sessions": sessions,
        "total_count": len(sessions),
        "tenant_id": current_user.tenant_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# WebSocket endpoints for signaling


@router.websocket("/client/{client_id}")
async def client_signaling_websocket(
    websocket: WebSocket, client_id: str, token: Optional[str] = None
):
    """WebSocket endpoint for client-side WebRTC signaling"""

    logger.info(f"Client WebRTC WebSocket connection: {client_id}")

    try:
        # Authenticate if token provided
        tenant_id = None
        if token:
            try:
                payload = verify_jwt(token)
                tenant_id = payload.get("tenant_id")
                logger.info(f"Client {client_id} authenticated for tenant {tenant_id}")
            except Exception as e:
                logger.warning(f"Client WebRTC authentication failed: {e}")
                await websocket.close(code=1008, reason="Authentication failed")
                return

        # Connect client
        await signaling_manager.connect_client(client_id, websocket, tenant_id)

        # Handle messages
        while True:
            try:
                data = await websocket.receive_text()
                message_data = json.loads(data)

                if message_data.get("type") == "signaling":
                    # Handle WebRTC signaling message
                    signaling_msg = WebRTCSignalingMessage(**message_data["data"])
                    await signaling_manager.handle_signaling_message(signaling_msg)

                elif message_data.get("type") == "ping":
                    # Respond to ping
                    await websocket.send_json({"type": "pong"})

                else:
                    logger.warning(
                        f"Unknown message type from client {client_id}: {message_data.get('type')}"
                    )

            except WebSocketDisconnect:
                break
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON from client {client_id}: {e}")
            except Exception as e:
                logger.error(f"Error handling client message: {e}")
                break

    except Exception as e:
        logger.error(f"Client WebSocket error: {e}")
    finally:
        signaling_manager.disconnect_client(client_id)


@router.websocket("/worker/{worker_id}")
async def worker_signaling_websocket(
    websocket: WebSocket, worker_id: str, token: Optional[str] = None
):
    """WebSocket endpoint for worker-side WebRTC signaling"""

    logger.info(f"Worker WebRTC WebSocket connection: {worker_id}")

    try:
        # Authenticate if token provided
        tenant_id = None
        if token:
            try:
                payload = verify_jwt(token)
                tenant_id = payload.get("tenant_id")

                # Verify worker exists and belongs to tenant
                worker = worker_registry.get_worker(worker_id)
                if not worker or worker.tenant_id != tenant_id:
                    logger.warning(
                        f"Worker {worker_id} not found or belongs to different tenant"
                    )
                    await websocket.close(code=1008, reason="Invalid worker")
                    return

                logger.info(f"Worker {worker_id} authenticated for tenant {tenant_id}")
            except Exception as e:
                logger.warning(f"Worker WebRTC authentication failed: {e}")
                await websocket.close(code=1008, reason="Authentication failed")
                return

        # Connect worker
        await signaling_manager.connect_worker(worker_id, websocket, tenant_id)

        # Handle messages
        while True:
            try:
                data = await websocket.receive_text()
                message_data = json.loads(data)

                if message_data.get("type") == "signaling":
                    # Handle WebRTC signaling message
                    signaling_msg = WebRTCSignalingMessage(**message_data["data"])
                    await signaling_manager.handle_signaling_message(signaling_msg)

                elif message_data.get("type") == "ping":
                    # Respond to ping
                    await websocket.send_json({"type": "pong"})

                else:
                    logger.warning(
                        f"Unknown message type from worker {worker_id}: {message_data.get('type')}"
                    )

            except WebSocketDisconnect:
                break
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON from worker {worker_id}: {e}")
            except Exception as e:
                logger.error(f"Error handling worker message: {e}")
                break

    except Exception as e:
        logger.error(f"Worker WebSocket error: {e}")
    finally:
        signaling_manager.disconnect_worker(worker_id)
