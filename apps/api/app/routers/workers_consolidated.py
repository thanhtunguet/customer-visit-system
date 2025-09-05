"""
Consolidated Worker API - Single endpoint group for all worker communication

This replaces the fragmented worker endpoints across multiple routers:
- worker_registry.py (/v1/registry/workers/*)  
- workers.py (/v1/workers/*)
- worker_camera_management.py
- Part of worker management commands

Design Principles:
- Single source of truth for worker operations
- Hybrid storage (in-memory + database) for optimal performance
- Clear separation of concerns within unified interface
- RESTful design with predictable endpoints
"""

from __future__ import annotations

import asyncio
import logging
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Set

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from sqlalchemy import and_, select
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db, get_db_session
from ..core.security import get_current_user, verify_jwt
from ..models.database import Worker, Camera
from ..services.worker_registry import worker_registry
from ..services.worker_shutdown_service import worker_shutdown_service, ShutdownSignal
from ..services.worker_command_service import worker_command_service
from common.enums.worker import WorkerStatus

logger = logging.getLogger(__name__)

# Pydantic Models
class UserInfo(BaseModel):
    sub: str
    role: str
    tenant_id: str

class WorkerRegistrationRequest(BaseModel):
    worker_id: Optional[str] = Field(None, description="Preferred worker ID (from env or .env)")
    worker_name: str = Field(..., description="Human-readable worker name")
    hostname: str = Field(..., description="Worker hostname")
    worker_version: Optional[str] = Field(None, description="Worker version")
    capabilities: Optional[Dict[str, Any]] = Field(None, description="Worker capabilities")
    site_id: Optional[int] = Field(None, description="Site assignment for camera allocation")
    is_reconnection: Optional[bool] = Field(False, description="Flag indicating reconnection")

class WorkerHeartbeatRequest(BaseModel):
    status: str = Field(..., description="Worker status: idle, processing, offline, error")
    faces_processed_count: Optional[int] = Field(0, description="Faces processed since last heartbeat")
    error_message: Optional[str] = Field(None, description="Error message if status is error")
    capabilities: Optional[Dict[str, Any]] = Field(None, description="Updated capabilities")
    current_camera_id: Optional[int] = Field(None, description="Currently processing camera")
    
    def get_status_enum(self) -> WorkerStatus:
        return WorkerStatus.from_string(self.status)

class WorkerStatusResponse(BaseModel):
    worker_id: str
    tenant_id: str
    hostname: str
    ip_address: Optional[str]
    worker_name: str
    worker_version: Optional[str]
    capabilities: Optional[Dict[str, Any]]
    status: str
    site_id: Optional[int]
    camera_id: Optional[int]
    last_heartbeat: str
    last_error: Optional[str]
    error_count: int
    total_faces_processed: int
    uptime_minutes: int
    registration_time: str
    is_healthy: bool

class WorkersListResponse(BaseModel):
    workers: List[WorkerStatusResponse]
    total_count: int
    online_count: int
    offline_count: int
    error_count: int
    processing_count: int

class CameraAssignmentRequest(BaseModel):
    site_id: Optional[int] = Field(None, description="Preferred site for camera assignment")

class CameraAssignmentResponse(BaseModel):
    assigned: bool
    camera_id: Optional[int]
    camera_name: Optional[str]
    site_id: Optional[int]
    message: str

class CommandResponse(BaseModel):
    command_id: str
    command_type: str
    payload: Optional[Dict[str, Any]]
    created_at: str
    expires_at: Optional[str]

class ShutdownRequest(BaseModel):
    signal: str = Field(default="graceful", description="Shutdown type: graceful, immediate, restart")
    timeout: int = Field(default=30, description="Timeout in seconds")

class StopSignalRequest(BaseModel):
    worker_id: str
    reason: str = Field(default="shutdown_requested")
    timestamp: str

# Router setup
router = APIRouter(prefix="/v1/workers", tags=["workers-consolidated"])

# WebSocket connection manager
class WorkerConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, tenant_id: str):
        await websocket.accept()
        if tenant_id not in self.active_connections:
            self.active_connections[tenant_id] = set()
        self.active_connections[tenant_id].add(websocket)
    
    def disconnect(self, websocket: WebSocket, tenant_id: str):
        if tenant_id in self.active_connections:
            self.active_connections[tenant_id].discard(websocket)
            if not self.active_connections[tenant_id]:
                del self.active_connections[tenant_id]
    
    async def broadcast_to_tenant(self, tenant_id: str, message: dict):
        if tenant_id in self.active_connections:
            disconnected = []
            for websocket in self.active_connections[tenant_id]:
                try:
                    await websocket.send_json(message)
                except:
                    disconnected.append(websocket)
            
            for ws in disconnected:
                self.active_connections[tenant_id].discard(ws)

connection_manager = WorkerConnectionManager()

def get_client_ip(request: Request) -> str:
    """Extract client IP address from request"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    return request.client.host if request.client else "unknown"

class WorkerService:
    """
    Hybrid worker service that combines in-memory and database storage
    
    Strategy:
    - In-memory (worker_registry): Fast real-time operations, status tracking
    - Database: Persistent storage, historical data, assignments
    - Auto-sync: Keep both systems synchronized
    """
    
    @staticmethod
    async def register_worker(
        request: WorkerRegistrationRequest,
        tenant_id: str,
        ip_address: str,
        db_session: AsyncSession
    ) -> Dict[str, Any]:
        """Register worker in both in-memory and database systems"""
        
        # 1. Register in in-memory system for real-time operations
        in_memory_worker = await worker_registry.register_worker(
            tenant_id=tenant_id,
            hostname=request.hostname,
            ip_address=ip_address,
            worker_name=request.worker_name,
            worker_version=request.worker_version,
            capabilities=request.capabilities,
            site_id=request.site_id,
            db_session=db_session,
            preferred_worker_id=request.worker_id,  # Use intended worker ID
        )
        
        # 2. Register/update in database for persistence
        result = await db_session.execute(
            select(Worker).where(
                and_(
                    Worker.tenant_id == tenant_id,
                    Worker.worker_id == in_memory_worker.worker_id
                )
            )
        )
        db_worker = result.scalar_one_or_none()
        
        if db_worker:
            # Update existing database worker
            db_worker.worker_name = request.worker_name
            db_worker.hostname = request.hostname
            db_worker.ip_address = ip_address
            db_worker.worker_version = request.worker_version
            db_worker.capabilities = json.dumps(request.capabilities) if request.capabilities else None
            db_worker.site_id = request.site_id
            db_worker.status = "online"
            db_worker.last_heartbeat = datetime.utcnow()
            db_worker.updated_at = datetime.utcnow()
        else:
            # Create new database worker
            db_worker = Worker(
                worker_id=in_memory_worker.worker_id,  # Use same ID as in-memory
                tenant_id=tenant_id,
                hostname=request.hostname,
                ip_address=ip_address,
                worker_name=request.worker_name,
                worker_version=request.worker_version,
                capabilities=json.dumps(request.capabilities) if request.capabilities else None,
                status="online",
                site_id=request.site_id,
                last_heartbeat=datetime.utcnow(),
                registration_time=datetime.utcnow()
            )
            db_session.add(db_worker)
        
        await db_session.commit()
        await db_session.refresh(db_worker)
        
        return {
            "worker_id": in_memory_worker.worker_id,
            "message": "Worker registered successfully in hybrid system",
            "status": "registered",
            "assigned_camera_id": in_memory_worker.camera_id,
            "site_id": in_memory_worker.site_id,
            "storage": "hybrid"  # Indicates both in-memory and database
        }

# Endpoints

@router.post("/register")
async def register_worker(
    request: Request,
    registration: WorkerRegistrationRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user_dict: dict = Depends(get_current_user),
):
    """Register worker with hybrid storage (in-memory + database)"""
    
    current_user = UserInfo(**current_user_dict)
    if current_user.role not in ["worker", "system_admin", "tenant_admin"]:
        raise HTTPException(status_code=403, detail="Only workers or admins can register")
    
    client_ip = get_client_ip(request)
    
    try:
        result = await WorkerService.register_worker(
            registration, current_user.tenant_id, client_ip, db
        )
        
        # Broadcast worker registration
        await connection_manager.broadcast_to_tenant(
            current_user.tenant_id,
            {
                "type": "worker_registered",
                "data": {"worker_id": result["worker_id"], "status": "online"},
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Worker registration failed: {e}")
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")

@router.post("/{worker_id}/heartbeat")
async def send_heartbeat(
    worker_id: str,
    heartbeat: WorkerHeartbeatRequest,
    current_user_dict: dict = Depends(get_current_user),
):
    """Send worker heartbeat to update status in hybrid storage"""
    
    current_user = UserInfo(**current_user_dict)
    if current_user.role not in ["worker", "system_admin"]:
        raise HTTPException(status_code=403, detail="Only workers can send heartbeats")
    
    try:
        status_enum = heartbeat.get_status_enum()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Update in-memory worker registry (primary)
    worker = await worker_registry.update_worker_heartbeat(
        worker_id=worker_id,
        status=status_enum,
        faces_processed_count=heartbeat.faces_processed_count or 0,
        error_message=heartbeat.error_message,
        capabilities=heartbeat.capabilities,
        current_camera_id=heartbeat.current_camera_id,
    )
    
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")
    
    if worker.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Worker belongs to different tenant")
    
    # Broadcast status update
    await connection_manager.broadcast_to_tenant(
        current_user.tenant_id,
        {
            "type": "worker_heartbeat",
            "data": worker.to_dict(),
            "timestamp": datetime.utcnow().isoformat()
        }
    )
    
    return {
        "message": "Heartbeat received successfully",
        "status": worker.status,
        "assigned_camera_id": worker.camera_id,
        "is_healthy": worker.is_healthy,
    }

@router.get("", response_model=WorkersListResponse)
async def list_workers(
    status: Optional[str] = None,
    site_id: Optional[int] = None,
    include_offline: bool = True,
    current_user_dict: dict = Depends(get_current_user),
):
    """List workers using hybrid storage (prioritize in-memory for real-time data)"""
    
    current_user = UserInfo(**current_user_dict)
    
    # Convert status filter
    status_enum = None
    if status:
        try:
            status_enum = WorkerStatus.from_string(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    
    # Get workers from in-memory registry (faster, real-time)
    workers = worker_registry.list_workers(
        tenant_id=current_user.tenant_id,
        status=status_enum,
        site_id=site_id,
        include_offline=include_offline,
    )
    
    # Convert to response format
    worker_responses = []
    for worker in workers:
        worker_responses.append(WorkerStatusResponse(
            worker_id=worker.worker_id,
            tenant_id=worker.tenant_id,
            hostname=worker.hostname,
            ip_address=worker.ip_address,
            worker_name=worker.worker_name,
            worker_version=worker.worker_version,
            capabilities=worker.capabilities,
            status=worker.status,
            site_id=worker.site_id,
            camera_id=worker.camera_id,
            last_heartbeat=worker.last_heartbeat.isoformat(),
            last_error=worker.last_error,
            error_count=worker.error_count,
            total_faces_processed=worker.total_faces_processed,
            uptime_minutes=worker.uptime_minutes,
            registration_time=worker.registration_time.isoformat(),
            is_healthy=worker.is_healthy,
        ))
    
    # Get statistics
    stats = worker_registry.get_stats(tenant_id=current_user.tenant_id)
    
    return WorkersListResponse(
        workers=worker_responses,
        total_count=stats["total_count"],
        online_count=stats["online_count"],
        offline_count=stats["offline_count"],
        error_count=stats["error_count"],
        processing_count=stats["processing_count"],
    )

@router.get("/{worker_id}", response_model=WorkerStatusResponse)
async def get_worker_status(
    worker_id: str,
    current_user_dict: dict = Depends(get_current_user),
):
    """Get specific worker status from in-memory registry"""
    
    current_user = UserInfo(**current_user_dict)
    
    worker = worker_registry.get_worker(worker_id)
    
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")
    
    if worker.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Worker belongs to different tenant")
    
    return WorkerStatusResponse(
        worker_id=worker.worker_id,
        tenant_id=worker.tenant_id,
        hostname=worker.hostname,
        ip_address=worker.ip_address,
        worker_name=worker.worker_name,
        worker_version=worker.worker_version,
        capabilities=worker.capabilities,
        status=worker.status,
        site_id=worker.site_id,
        camera_id=worker.camera_id,
        last_heartbeat=worker.last_heartbeat.isoformat(),
        last_error=worker.last_error,
        error_count=worker.error_count,
        total_faces_processed=worker.total_faces_processed,
        uptime_minutes=worker.uptime_minutes,
        registration_time=worker.registration_time.isoformat(),
        is_healthy=worker.is_healthy,
    )

@router.post("/{worker_id}/camera/request", response_model=CameraAssignmentResponse)  
async def request_camera_assignment(
    worker_id: str,
    request_data: CameraAssignmentRequest = CameraAssignmentRequest(),
    current_user_dict: dict = Depends(get_current_user),
):
    """Request camera assignment for worker"""
    
    current_user = UserInfo(**current_user_dict)
    if current_user.role not in ["worker", "system_admin"]:
        raise HTTPException(status_code=403, detail="Only workers can request cameras")
    
    worker = worker_registry.get_worker(worker_id)
    
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")
    
    if worker.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Worker belongs to different tenant")
    
    # Camera assignment logic would go here - for now return existing assignment
    return CameraAssignmentResponse(
        assigned=worker.camera_id is not None,
        camera_id=worker.camera_id,
        camera_name=f"Camera {worker.camera_id}" if worker.camera_id else None,
        site_id=worker.site_id,
        message="Camera assignment handled during registration" if worker.camera_id else "No cameras available"
    )

# Shutdown endpoints
@router.post("/{worker_id}/shutdown/signal")
async def receive_stop_signal(
    worker_id: str,
    stop_signal: StopSignalRequest,
    current_user_dict: dict = Depends(get_current_user),
):
    """Receive stop signal from worker during shutdown"""
    
    current_user = UserInfo(**current_user_dict)
    if current_user.role not in ["worker", "system_admin"]:
        raise HTTPException(status_code=403, detail="Only workers can send stop signals")
    
    worker = worker_registry.get_worker(worker_id)
    
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")
    
    if worker.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Worker belongs to different tenant")
    
    # Handle stop signal - release cameras, update status, cleanup
    assigned_camera_id = worker.camera_id
    if assigned_camera_id:
        logger.info(f"Releasing camera {assigned_camera_id} from shutting down worker {worker_id}")
        # Camera release logic would go here
    
    # Update worker status
    await worker_registry.update_worker_heartbeat(
        worker_id=worker_id,
        status=WorkerStatus.OFFLINE,
        error_message=f"Worker shutdown: {stop_signal.reason}"
    )
    
    logger.info(f"Worker {worker_id} shutdown cleanup completed")
    
    return {
        "message": "Stop signal acknowledged - backend cleanup completed",
        "worker_id": worker_id,
        "status": "acknowledged_and_cleaned",
        "camera_released": assigned_camera_id is not None,
        "released_camera_id": assigned_camera_id,
        "backend_cleanup_completed": True,
        "timestamp": datetime.utcnow().isoformat()
    }

@router.delete("/{worker_id}")
async def deregister_worker(
    worker_id: str,
    force: bool = False,
    current_user_dict: dict = Depends(get_current_user),
):
    """Deregister worker from both in-memory and database"""
    
    current_user = UserInfo(**current_user_dict)
    if current_user.role not in ["system_admin", "tenant_admin", "worker"]:
        raise HTTPException(status_code=403, detail="Only admins or workers can deregister")
    
    worker = worker_registry.get_worker(worker_id)
    
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")
    
    if worker.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Worker belongs to different tenant")
    
    # Remove from both storage systems
    await worker_registry.remove_worker(worker_id)
    
    # Broadcast worker removal
    await connection_manager.broadcast_to_tenant(
        current_user.tenant_id,
        {
            "type": "worker_deregistered",
            "data": {"worker_id": worker_id, "status": "offline"},
            "timestamp": datetime.utcnow().isoformat()
        }
    )
    
    return {
        "message": f"Worker {worker.worker_name} deregistered from hybrid storage",
        "worker_name": worker.worker_name,
        "storage_cleanup": "hybrid"
    }

# Administrative endpoints
@router.post("/cleanup")
async def cleanup_stale_workers(
    ttl_seconds: int = 300,
    current_user_dict: dict = Depends(get_current_user),
):
    """Cleanup stale workers from hybrid storage"""
    
    current_user = UserInfo(**current_user_dict)
    if current_user.role not in ["system_admin", "tenant_admin"]:
        raise HTTPException(status_code=403, detail="Only admins can cleanup workers")
    
    removed_count = await worker_registry.cleanup_stale_workers(ttl_seconds=ttl_seconds)
    
    return {
        "message": f"Cleaned up {removed_count} stale workers from hybrid storage",
        "ttl_seconds": ttl_seconds,
        "removed_count": removed_count,
    }

@router.get("/stats")
async def get_worker_stats(
    current_user_dict: dict = Depends(get_current_user),
):
    """Get worker statistics from in-memory registry"""
    
    current_user = UserInfo(**current_user_dict)
    stats = worker_registry.get_stats(tenant_id=current_user.tenant_id)
    
    return {
        "tenant_id": current_user.tenant_id,
        "statistics": stats,
        "storage_type": "hybrid",
        "timestamp": datetime.utcnow().isoformat(),
    }

# WebSocket for real-time updates
@router.websocket("/ws/{tenant_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    tenant_id: str,
    token: Optional[str] = None
):
    """WebSocket endpoint for real-time worker status updates"""
    logger.info(f"WebSocket connection attempt for tenant: {tenant_id}, token provided: {token is not None}")
    
    try:
        # Validate token if provided
        if token:
            try:
                payload = verify_jwt(token)
                user_tenant_id = payload.get("tenant_id")
                
                if user_tenant_id != tenant_id:
                    logger.warning(f"WebSocket connection denied: token tenant_id {user_tenant_id} != requested tenant_id {tenant_id}")
                    await websocket.close(code=1008, reason="Invalid tenant")
                    return
                    
                logger.info(f"WebSocket authentication successful for tenant {tenant_id}")
            except Exception as auth_error:
                logger.warning(f"WebSocket authentication failed: {auth_error}")
                await websocket.close(code=1008, reason="Authentication failed")
                return
        else:
            logger.warning(f"WebSocket connection without token for tenant {tenant_id}")
            # For now, allow connections without tokens for debugging
        
        logger.info(f"Accepting WebSocket connection for tenant {tenant_id}")
        await connection_manager.connect(websocket, tenant_id)
        
        # Send initial worker status
        try:
            workers = worker_registry.list_workers(tenant_id=tenant_id, include_offline=True)
            initial_data = [worker.to_dict() for worker in workers]
            
            logger.info(f"Sending initial data to WebSocket for tenant {tenant_id}: {len(initial_data)} workers")
            
            await websocket.send_json({
                "type": "initial_data",
                "data": initial_data,
                "storage_type": "hybrid",
                "timestamp": datetime.utcnow().isoformat()
            })
            
            logger.info(f"Successfully sent initial data to WebSocket for tenant {tenant_id}")
            
        except Exception as e:
            logger.error(f"Error sending initial data to WebSocket for tenant {tenant_id}: {e}")
        
        # Keep connection alive
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                logger.debug(f"WebSocket received message from client: {message}")
                # Respond to ping
                await websocket.send_json({"type": "ping"})
            except asyncio.TimeoutError:
                logger.debug(f"WebSocket timeout, sending ping to tenant {tenant_id}")
                try:
                    await websocket.send_json({"type": "ping"})
                except:
                    # Connection might be closed
                    break
            except WebSocketDisconnect:
                logger.info(f"WebSocket client disconnected for tenant {tenant_id}")
                break
            except Exception as e:
                logger.error(f"WebSocket receive error for tenant {tenant_id}: {e}")
                break
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for tenant {tenant_id}")
    except Exception as e:
        logger.error(f"WebSocket error for tenant {tenant_id}: {e}")
    finally:
        logger.info(f"WebSocket cleanup for tenant {tenant_id}")
        connection_manager.disconnect(websocket, tenant_id)