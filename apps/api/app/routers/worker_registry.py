from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from ..core.security import get_current_user
from ..services.worker_registry import worker_registry, WorkerInfo
from ..enums import WorkerStatus

logger = logging.getLogger(__name__)


class UserInfo(BaseModel):
    sub: str
    role: str
    tenant_id: str


class WorkerRegistrationRequest(BaseModel):
    worker_name: str = Field(..., description="Human-readable worker name")
    hostname: str = Field(..., description="Worker hostname")
    worker_version: Optional[str] = Field(None, description="Worker version")
    capabilities: Optional[Dict[str, Any]] = Field(None, description="Worker capabilities")
    site_id: Optional[int] = Field(None, description="Optional site assignment")
    camera_id: Optional[int] = Field(None, description="Optional camera assignment")


class WorkerHeartbeatRequest(BaseModel):
    status: str = Field(..., description="Worker status: idle, processing, offline, error, maintenance")
    faces_processed_count: Optional[int] = Field(0, description="Number of faces processed since last heartbeat")
    error_message: Optional[str] = Field(None, description="Error message if status is error")
    capabilities: Optional[Dict[str, Any]] = Field(None, description="Updated worker capabilities")
    current_camera_id: Optional[int] = Field(None, description="Camera currently being processed by worker")
    
    def get_status_enum(self) -> WorkerStatus:
        """Convert string status to WorkerStatus enum"""
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


router = APIRouter(prefix="/v1/registry", tags=["worker-registry"])


# WebSocket connection manager for real-time updates
class WorkerConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, set] = {}
    
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
            
            # Remove disconnected websockets
            for ws in disconnected:
                self.active_connections[tenant_id].discard(ws)
    
    async def broadcast_worker_update(self, event_type: str, worker_info: WorkerInfo):
        message = {
            "type": event_type,
            "data": worker_info.to_dict(),
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.broadcast_to_tenant(worker_info.tenant_id, message)


# Global connection manager
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


# Worker status change callback
async def on_worker_status_change(event_type: str, worker_info: WorkerInfo):
    """Callback for worker status changes"""
    try:
        await connection_manager.broadcast_worker_update(event_type, worker_info)
        logger.debug(f"Broadcasted {event_type} for worker {worker_info.worker_id}")
    except Exception as e:
        logger.error(f"Error broadcasting worker status change: {e}")


# Register the callback
worker_registry.add_status_callback(on_worker_status_change)


@router.post("/workers/register")
async def register_worker(
    request: Request,
    registration: WorkerRegistrationRequest,
    current_user_dict: dict = Depends(get_current_user),
):
    """Register a new worker in the in-memory registry"""
    
    # Only workers can register themselves
    current_user = UserInfo(**current_user_dict)
    if current_user.role not in ["worker", "system_admin", "tenant_admin"]:
        raise HTTPException(
            status_code=403,
            detail="Only workers or admins can register workers"
        )
    
    client_ip = get_client_ip(request)
    
    # Register worker in memory
    worker = await worker_registry.register_worker(
        tenant_id=current_user.tenant_id,
        hostname=registration.hostname,
        ip_address=client_ip,
        worker_name=registration.worker_name,
        worker_version=registration.worker_version,
        capabilities=registration.capabilities,
        site_id=registration.site_id,
        camera_id=registration.camera_id,
    )
    
    return {
        "worker_id": worker.worker_id,
        "message": f"Worker registered successfully as {worker.worker_name}",
        "status": "registered",
        "assigned_camera_id": worker.camera_id,
        "site_id": worker.site_id,
    }


@router.post("/workers/{worker_id}/heartbeat")
async def send_heartbeat(
    worker_id: str,
    heartbeat: WorkerHeartbeatRequest,
    current_user_dict: dict = Depends(get_current_user),
):
    """Send worker heartbeat to update status"""
    
    # Only workers can send heartbeats
    current_user = UserInfo(**current_user_dict)
    if current_user.role not in ["worker", "system_admin"]:
        raise HTTPException(
            status_code=403,
            detail="Only workers or system admins can send heartbeats"
        )
    
    # Update heartbeat
    try:
        status_enum = heartbeat.get_status_enum()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
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
    
    # Verify worker belongs to current tenant
    if worker.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Worker belongs to different tenant")
    
    return {
        "message": "Heartbeat received successfully",
        "status": worker.status,
        "assigned_camera_id": worker.camera_id,
        "is_healthy": worker.is_healthy,
    }


@router.get("/workers", response_model=WorkersListResponse)
async def list_workers(
    status: Optional[str] = None,
    site_id: Optional[int] = None,
    include_offline: bool = True,
    current_user_dict: dict = Depends(get_current_user),
):
    """List all workers with their status"""
    
    current_user = UserInfo(**current_user_dict)
    
    # Convert status string to enum if provided
    status_enum = None
    if status:
        try:
            status_enum = WorkerStatus.from_string(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    
    # Get workers from registry
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


@router.get("/workers/{worker_id}", response_model=WorkerStatusResponse)
async def get_worker_status(
    worker_id: str,
    current_user_dict: dict = Depends(get_current_user),
):
    """Get specific worker status"""
    
    current_user = UserInfo(**current_user_dict)
    
    worker = worker_registry.get_worker(worker_id)
    
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")
    
    # Verify worker belongs to current tenant
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


@router.delete("/workers/{worker_id}")
async def deregister_worker(
    worker_id: str,
    current_user_dict: dict = Depends(get_current_user),
):
    """Remove worker from registry"""
    
    current_user = UserInfo(**current_user_dict)
    
    # Only admins or workers themselves can deregister
    if current_user.role not in ["system_admin", "tenant_admin", "worker"]:
        raise HTTPException(
            status_code=403,
            detail="Only admins or workers can deregister workers"
        )
    
    worker = worker_registry.get_worker(worker_id)
    
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")
    
    # Verify worker belongs to current tenant
    if worker.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Worker belongs to different tenant")
    
    # Remove worker
    success = await worker_registry.remove_worker(worker_id)
    
    if success:
        return {
            "message": f"Worker {worker.worker_name} deregistered successfully",
            "worker_name": worker.worker_name,
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to deregister worker")


@router.post("/workers/cleanup-stale")
async def cleanup_stale_workers(
    ttl_seconds: int = 300,  # 5 minutes default
    current_user_dict: dict = Depends(get_current_user),
):
    """Cleanup workers that haven't sent heartbeat for specified seconds"""
    
    current_user = UserInfo(**current_user_dict)
    
    # Only admins can cleanup stale workers
    if current_user.role not in ["system_admin", "tenant_admin"]:
        raise HTTPException(
            status_code=403,
            detail="Only admins can cleanup stale workers"
        )
    
    removed_count = await worker_registry.cleanup_stale_workers(ttl_seconds=ttl_seconds)
    
    return {
        "message": f"Cleaned up {removed_count} stale workers",
        "ttl_seconds": ttl_seconds,
        "removed_count": removed_count,
    }


@router.get("/workers/stats")
async def get_worker_stats(
    current_user_dict: dict = Depends(get_current_user),
):
    """Get worker registry statistics"""
    
    current_user = UserInfo(**current_user_dict)
    stats = worker_registry.get_stats(tenant_id=current_user.tenant_id)
    
    return {
        "tenant_id": current_user.tenant_id,
        "statistics": stats,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.websocket("/workers/ws/{tenant_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    tenant_id: str,
    token: Optional[str] = None
):
    """WebSocket endpoint for real-time worker status updates"""
    try:
        await connection_manager.connect(websocket, tenant_id)
        
        # Send initial worker status
        try:
            workers = worker_registry.list_workers(tenant_id=tenant_id, include_offline=True)
            initial_data = [worker.to_dict() for worker in workers]
            
            await websocket.send_json({
                "type": "initial_data",
                "data": initial_data,
                "timestamp": datetime.utcnow().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error sending initial data: {e}")
        
        # Keep connection alive
        while True:
            try:
                # Wait for ping/pong to keep connection alive
                await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                # Send ping to keep connection alive
                await websocket.send_json({"type": "ping"})
            except WebSocketDisconnect:
                break
                
    except WebSocketDisconnect:
        pass
    finally:
        connection_manager.disconnect(websocket, tenant_id)