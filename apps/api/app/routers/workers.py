from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from pydantic import BaseModel, Field
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from ..core.database import get_db, get_db_session
from ..core.security import get_current_user
from ..models.database import Camera, Worker
from ..services.worker_shutdown_service import ShutdownSignal, worker_shutdown_service

logger = logging.getLogger(__name__)


class UserInfo(BaseModel):
    sub: str
    role: str
    tenant_id: str


class WorkerRegistrationRequest(BaseModel):
    worker_name: str = Field(..., description="Human-readable worker name")
    hostname: str = Field(..., description="Worker hostname")
    worker_version: Optional[str] = Field(None, description="Worker version")
    capabilities: Optional[Dict[str, Any]] = Field(
        None, description="Worker capabilities"
    )
    site_id: Optional[int] = Field(None, description="Optional site assignment")
    camera_id: Optional[int] = Field(None, description="Optional camera assignment")


class WorkerHeartbeatRequest(BaseModel):
    status: str = Field(
        ..., description="Worker status: idle, processing, offline, error, maintenance"
    )
    faces_processed_count: Optional[int] = Field(
        0, description="Number of faces processed since last heartbeat"
    )
    error_message: Optional[str] = Field(
        None, description="Error message if status is error"
    )
    capabilities: Optional[Dict[str, Any]] = Field(
        None, description="Updated worker capabilities"
    )
    current_camera_id: Optional[int] = Field(
        None, description="Camera currently being processed by worker"
    )


class WorkerShutdownRequest(BaseModel):
    signal: str = Field(
        default="graceful", description="Shutdown signal: graceful, immediate, restart"
    )
    timeout: int = Field(
        default=30, description="Timeout in seconds for graceful shutdown"
    )


class WorkerShutdownResponse(BaseModel):
    success: bool
    message: str
    shutdown_id: Optional[str] = None
    timeout: Optional[int] = None
    error: Optional[str] = None


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
    last_heartbeat: Optional[datetime]
    last_error: Optional[str]
    error_count: int
    total_faces_processed: int
    uptime_minutes: Optional[int]
    registration_time: datetime
    is_healthy: bool


class WorkersListResponse(BaseModel):
    workers: List[WorkerStatusResponse]
    total_count: int
    online_count: int
    offline_count: int
    error_count: int


router = APIRouter(prefix="/v1", tags=["workers"])


# WebSocket connection manager for real-time updates
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
                except Exception:
                    disconnected.append(websocket)

            # Remove disconnected websockets
            for ws in disconnected:
                self.active_connections[tenant_id].discard(ws)

    async def broadcast_worker_update(self, tenant_id: str, worker_data: dict):
        message = {
            "type": "worker_update",
            "data": worker_data,
            "timestamp": datetime.utcnow().isoformat(),
        }
        await self.broadcast_to_tenant(tenant_id, message)

    async def broadcast_worker_list_update(self, tenant_id: str):
        """Broadcast complete worker list update for major changes"""
        message = {
            "type": "worker_list_refresh",
            "timestamp": datetime.utcnow().isoformat(),
        }
        await self.broadcast_to_tenant(tenant_id, message)


# Global connection manager
connection_manager = WorkerConnectionManager()


async def broadcast_worker_status_update(worker: Worker, tenant_id: str):
    """Broadcast worker status update via WebSocket"""
    try:
        import json

        # Parse capabilities
        capabilities = None
        if worker.capabilities:
            try:
                capabilities = json.loads(worker.capabilities)
            except json.JSONDecodeError:
                capabilities = None

        worker_data = {
            "worker_id": worker.worker_id,
            "tenant_id": worker.tenant_id,
            "hostname": worker.hostname,
            "ip_address": worker.ip_address,
            "worker_name": worker.worker_name,
            "worker_version": worker.worker_version,
            "capabilities": capabilities,
            "status": worker.status,
            "site_id": worker.site_id,
            "camera_id": worker.camera_id,
            "last_heartbeat": (
                worker.last_heartbeat.isoformat() if worker.last_heartbeat else None
            ),
            "last_error": worker.last_error,
            "error_count": worker.error_count,
            "total_faces_processed": worker.total_faces_processed,
            "uptime_minutes": calculate_uptime_minutes(worker),
            "registration_time": (
                worker.registration_time.isoformat()
                if worker.registration_time
                else None
            ),
            "is_healthy": is_worker_healthy(worker),
        }

        # Broadcast update
        await connection_manager.broadcast_worker_update(tenant_id, worker_data)
        logger.info(
            f"Broadcasted worker update for {worker.worker_id} to tenant {tenant_id}"
        )

    except Exception as e:
        logger.error(f"Error broadcasting worker status update: {e}")


def assign_camera_to_worker(
    db: Session, tenant_id: str, site_id: int, worker_id: str
) -> Optional[Camera]:
    """
    Assign an available camera to a worker. Enforces one-camera-per-worker constraint.

    Args:
        db: Database session
        tenant_id: Tenant ID for RLS
        site_id: Site ID where worker should be assigned
        worker_id: Worker ID to assign camera to

    Returns:
        Camera object if assignment successful, None if no cameras available
    """

    # Find all cameras in the site for this tenant
    available_cameras = (
        db.query(Camera)
        .filter(
            and_(
                Camera.tenant_id == tenant_id,
                Camera.site_id == site_id,
                Camera.is_active,
            )
        )
        .all()
    )

    if not available_cameras:
        return None

    # Find cameras that are not currently assigned to any active worker
    assigned_camera_ids = set()
    active_workers = (
        db.query(Worker)
        .filter(
            and_(
                Worker.tenant_id == tenant_id,
                Worker.site_id == site_id,
                Worker.camera_id.isnot(None),
                Worker.status.in_(
                    ["idle", "processing", "online"]
                ),  # Consider these as active
            )
        )
        .all()
    )

    for worker in active_workers:
        if (
            worker.worker_id != worker_id and worker.camera_id
        ):  # Don't count current worker
            assigned_camera_ids.add(worker.camera_id)

    # Find first available camera
    for camera in available_cameras:
        if camera.camera_id not in assigned_camera_ids:
            return camera

    # No available cameras
    return None


def release_worker_camera(db: Session, worker_id: str):
    """
    Release camera assignment from a worker (e.g., when worker goes offline)

    Args:
        db: Database session
        worker_id: Worker ID to release camera from
    """
    worker = db.query(Worker).filter(Worker.worker_id == worker_id).first()
    if worker:
        worker.camera_id = None
        worker.status = "offline"
        db.commit()


def get_client_ip(request: Request) -> str:
    """Extract client IP address from request"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    return request.client.host if request.client else "unknown"


def is_worker_healthy(worker: Worker) -> bool:
    """Check if worker is considered healthy based on last heartbeat"""
    if not worker.last_heartbeat:
        return False

    # Worker must be in active status
    if worker.status not in ["idle", "processing", "online"]:
        return False

    # Consider worker unhealthy if no heartbeat for 2 minutes
    stale_threshold = datetime.utcnow() - timedelta(minutes=2)
    return worker.last_heartbeat > stale_threshold


def calculate_uptime_minutes(worker: Worker) -> Optional[int]:
    """Calculate worker uptime in minutes"""
    if not worker.registration_time:
        return None

    if worker.status != "online" or not worker.last_heartbeat:
        return 0

    uptime = worker.last_heartbeat - worker.registration_time
    return int(uptime.total_seconds() / 60)


@router.post("/workers/register", response_model=Dict[str, str])
async def register_worker(
    request: Request,
    registration: WorkerRegistrationRequest,
    db: Session = Depends(get_db),
    current_user_dict: dict = Depends(get_current_user),
):
    """Register a new worker and automatically assign an available camera from the specified site"""

    # Only workers can register themselves
    current_user = UserInfo(**current_user_dict)
    if current_user.role not in ["worker", "system_admin", "tenant_admin"]:
        raise HTTPException(
            status_code=403, detail="Only workers or admins can register workers"
        )

    # Validate site_id is required for camera assignment
    if not registration.site_id:
        raise HTTPException(
            status_code=400, detail="site_id is required for worker registration"
        )

    client_ip = get_client_ip(request)

    # Check if worker with same hostname already exists for this tenant
    existing_worker = (
        db.query(Worker)
        .filter(
            and_(
                Worker.tenant_id == current_user.tenant_id,
                Worker.hostname == registration.hostname,
            )
        )
        .first()
    )

    if existing_worker:
        # For existing worker, reassign camera if needed
        assigned_camera = assign_camera_to_worker(
            db, current_user.tenant_id, registration.site_id, existing_worker.worker_id
        )

        # Update existing worker registration
        existing_worker.worker_name = registration.worker_name
        existing_worker.ip_address = client_ip
        existing_worker.worker_version = registration.worker_version
        existing_worker.capabilities = (
            json.dumps(registration.capabilities) if registration.capabilities else None
        )
        existing_worker.site_id = registration.site_id
        existing_worker.camera_id = (
            assigned_camera.camera_id if assigned_camera else None
        )
        existing_worker.status = (
            "idle"  # Start as idle, will become 'processing' when working
        )
        existing_worker.last_heartbeat = datetime.utcnow()
        existing_worker.registration_time = datetime.utcnow()
        existing_worker.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(existing_worker)

        # Trigger WebSocket update for existing worker
        await broadcast_worker_status_update(existing_worker, current_user.tenant_id)

        response = {
            "worker_id": existing_worker.worker_id,
            "message": "Worker registration updated successfully",
            "status": "updated",
        }

        if assigned_camera:
            response["assigned_camera_id"] = str(assigned_camera.camera_id)
            response["assigned_camera_name"] = assigned_camera.name
            response[
                "message"
            ] += f" and assigned to camera {assigned_camera.camera_id} ({assigned_camera.name})"
        else:
            response["message"] += " but no available cameras to assign"

        return response

    # Create new worker registration
    new_worker = Worker(
        tenant_id=current_user.tenant_id,
        hostname=registration.hostname,
        ip_address=client_ip,
        worker_name=registration.worker_name,
        worker_version=registration.worker_version,
        capabilities=(
            json.dumps(registration.capabilities) if registration.capabilities else None
        ),
        status="idle",  # Start as idle
        site_id=registration.site_id,
        camera_id=None,  # Will be assigned below
        last_heartbeat=datetime.utcnow(),
        registration_time=datetime.utcnow(),
    )

    db.add(new_worker)
    db.flush()  # Get the worker_id without committing

    # Assign an available camera to this worker
    assigned_camera = assign_camera_to_worker(
        db, current_user.tenant_id, registration.site_id, new_worker.worker_id
    )

    if assigned_camera:
        new_worker.camera_id = assigned_camera.camera_id

    db.commit()
    db.refresh(new_worker)

    # Trigger WebSocket update for new worker
    await broadcast_worker_status_update(new_worker, current_user.tenant_id)

    response = {
        "worker_id": new_worker.worker_id,
        "message": "Worker registered successfully",
        "status": "registered",
    }

    if assigned_camera:
        response["assigned_camera_id"] = str(assigned_camera.camera_id)
        response["assigned_camera_name"] = assigned_camera.name
        response[
            "message"
        ] += f" and assigned to camera {assigned_camera.camera_id} ({assigned_camera.name})"
    else:
        response["message"] += " but no available cameras to assign"

    return response


@router.post("/workers/{worker_id}/heartbeat")
async def send_heartbeat(
    worker_id: str,
    heartbeat: WorkerHeartbeatRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user_dict: dict = Depends(get_current_user),
):
    """Send worker heartbeat to update status"""

    # Only workers can send heartbeats
    current_user = UserInfo(**current_user_dict)
    if current_user.role not in ["worker", "system_admin"]:
        raise HTTPException(
            status_code=403, detail="Only workers or system admins can send heartbeats"
        )

    # Find worker using async query
    from sqlalchemy import and_, select

    result = await db.execute(
        select(Worker).where(
            and_(
                Worker.worker_id == worker_id,
                Worker.tenant_id == current_user.tenant_id,
            )
        )
    )
    worker = result.scalar_one_or_none()

    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")

    # Update worker status
    old_status = worker.status
    worker.status = heartbeat.status
    worker.last_heartbeat = datetime.utcnow()
    worker.updated_at = datetime.utcnow()

    # Handle status transitions
    if old_status != heartbeat.status:
        if heartbeat.status == "offline":
            # Worker going offline - release camera assignment
            worker.camera_id = None
        elif heartbeat.status in ["idle", "online"] and not worker.camera_id:
            # Worker becoming idle/online but has no camera - try to assign one
            # TODO: Convert assign_camera_to_worker to async or disable temporarily
            pass
        elif heartbeat.status == "processing" and heartbeat.current_camera_id:
            # Verify worker is processing the correct assigned camera
            if worker.camera_id and worker.camera_id != heartbeat.current_camera_id:
                # Worker is processing different camera than assigned - this might be an error
                worker.last_error = f"Worker processing camera {heartbeat.current_camera_id} but assigned to {worker.camera_id}"

    # Update faces processed count
    if heartbeat.faces_processed_count and heartbeat.faces_processed_count > 0:
        worker.total_faces_processed += heartbeat.faces_processed_count

    # Update capabilities if provided
    if heartbeat.capabilities:
        worker.capabilities = json.dumps(heartbeat.capabilities)

    # Handle error status
    if heartbeat.status == "error":
        worker.error_count += 1
        worker.last_error = heartbeat.error_message
    elif heartbeat.status == "online":
        # Clear error when worker comes back online
        worker.last_error = None

    # Commit changes
    await db.commit()
    await db.refresh(worker)

    # Broadcast worker update to WebSocket clients
    try:
        capabilities = None
        if worker.capabilities:
            try:
                capabilities = json.loads(worker.capabilities)
            except json.JSONDecodeError:
                capabilities = None

        worker_data = {
            "worker_id": worker.worker_id,
            "tenant_id": worker.tenant_id,
            "hostname": worker.hostname,
            "ip_address": worker.ip_address,
            "worker_name": worker.worker_name,
            "worker_version": worker.worker_version,
            "capabilities": capabilities,
            "status": worker.status,
            "site_id": worker.site_id,
            "camera_id": worker.camera_id,
            "last_heartbeat": (
                worker.last_heartbeat.isoformat() if worker.last_heartbeat else None
            ),
            "last_error": worker.last_error,
            "error_count": worker.error_count,
            "total_faces_processed": worker.total_faces_processed,
            "uptime_minutes": calculate_uptime_minutes(worker),
            "registration_time": worker.registration_time.isoformat(),
            "is_healthy": is_worker_healthy(worker),
        }

        # Use task manager to avoid blocking and prevent resource leaks
        from ..core.task_manager import create_broadcast_task

        create_broadcast_task(
            connection_manager.broadcast_worker_update(
                current_user.tenant_id, worker_data
            ),
            name="worker_broadcast",
        )
    except Exception as e:
        print(f"Error broadcasting worker update: {e}")

    return {
        "message": "Heartbeat received successfully",
        "status": worker.status,
        "assigned_camera_id": worker.camera_id,
    }


@router.post("/workers/{worker_id}/request-camera")
async def request_camera_assignment(
    worker_id: str,
    db: Session = Depends(get_db),
    current_user_dict: dict = Depends(get_current_user),
):
    """Request camera assignment for a worker"""

    current_user = UserInfo(**current_user_dict)
    if current_user.role not in ["worker", "system_admin"]:
        raise HTTPException(
            status_code=403,
            detail="Only workers or system admins can request camera assignments",
        )

    # Find worker
    worker = (
        db.query(Worker)
        .filter(
            and_(
                Worker.worker_id == worker_id,
                Worker.tenant_id == current_user.tenant_id,
            )
        )
        .first()
    )

    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")

    if not worker.site_id:
        raise HTTPException(
            status_code=400, detail="Worker must be assigned to a site first"
        )

    # Try to assign a camera
    assigned_camera = assign_camera_to_worker(
        db, current_user.tenant_id, worker.site_id, worker_id
    )

    if assigned_camera:
        worker.camera_id = assigned_camera.camera_id
        worker.status = "idle"
        worker.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(worker)

        # Broadcast worker update
        await broadcast_worker_status_update(worker, current_user.tenant_id)

        return {
            "message": f"Camera {assigned_camera.camera_id} ({assigned_camera.name}) assigned successfully",
            "assigned_camera_id": assigned_camera.camera_id,
            "assigned_camera_name": assigned_camera.name,
            "worker_status": "idle",
        }
    else:
        return {
            "message": "No available cameras to assign",
            "assigned_camera_id": None,
            "worker_status": worker.status,
        }


@router.get("/workers", response_model=WorkersListResponse)
async def list_workers(
    status: Optional[str] = None,
    site_id: Optional[int] = None,
    include_offline: bool = True,
    db: Session = Depends(get_db),
    current_user_dict: dict = Depends(get_current_user),
):
    """List all workers with their status"""

    current_user = UserInfo(**current_user_dict)

    # Build query
    query = db.query(Worker).filter(Worker.tenant_id == current_user.tenant_id)

    if status:
        query = query.filter(Worker.status == status)

    if site_id:
        query = query.filter(Worker.site_id == site_id)

    if not include_offline:
        query = query.filter(Worker.status != "offline")

    workers = query.order_by(Worker.last_heartbeat.desc().nullslast()).all()

    # Build response data
    worker_responses = []
    for worker in workers:
        # Parse capabilities
        capabilities = None
        if worker.capabilities:
            try:
                capabilities = json.loads(worker.capabilities)
            except json.JSONDecodeError:
                capabilities = None

        worker_responses.append(
            WorkerStatusResponse(
                worker_id=worker.worker_id,
                tenant_id=worker.tenant_id,
                hostname=worker.hostname,
                ip_address=worker.ip_address,
                worker_name=worker.worker_name,
                worker_version=worker.worker_version,
                capabilities=capabilities,
                status=worker.status,
                site_id=worker.site_id,
                camera_id=worker.camera_id,
                last_heartbeat=worker.last_heartbeat,
                last_error=worker.last_error,
                error_count=worker.error_count,
                total_faces_processed=worker.total_faces_processed,
                uptime_minutes=calculate_uptime_minutes(worker),
                registration_time=worker.registration_time,
                is_healthy=is_worker_healthy(worker),
            )
        )

    # Calculate summary statistics
    total_count = len(worker_responses)
    online_count = sum(
        1 for w in worker_responses if w.status == "online" and w.is_healthy
    )
    offline_count = sum(
        1 for w in worker_responses if w.status == "offline" or not w.is_healthy
    )
    error_count = sum(1 for w in worker_responses if w.status == "error")

    return WorkersListResponse(
        workers=worker_responses,
        total_count=total_count,
        online_count=online_count,
        offline_count=offline_count,
        error_count=error_count,
    )


@router.get("/workers/{worker_id}", response_model=WorkerStatusResponse)
async def get_worker_status(
    worker_id: str,
    db: Session = Depends(get_db),
    current_user_dict: dict = Depends(get_current_user),
):
    """Get specific worker status"""

    current_user = UserInfo(**current_user_dict)

    worker = (
        db.query(Worker)
        .filter(
            and_(
                Worker.worker_id == worker_id,
                Worker.tenant_id == current_user.tenant_id,
            )
        )
        .first()
    )

    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")

    # Parse capabilities
    capabilities = None
    if worker.capabilities:
        try:
            capabilities = json.loads(worker.capabilities)
        except json.JSONDecodeError:
            capabilities = None

    return WorkerStatusResponse(
        worker_id=worker.worker_id,
        tenant_id=worker.tenant_id,
        hostname=worker.hostname,
        ip_address=worker.ip_address,
        worker_name=worker.worker_name,
        worker_version=worker.worker_version,
        capabilities=capabilities,
        status=worker.status,
        site_id=worker.site_id,
        camera_id=worker.camera_id,
        last_heartbeat=worker.last_heartbeat,
        last_error=worker.last_error,
        error_count=worker.error_count,
        total_faces_processed=worker.total_faces_processed,
        uptime_minutes=calculate_uptime_minutes(worker),
        registration_time=worker.registration_time,
        is_healthy=is_worker_healthy(worker),
    )


@router.delete("/workers/{worker_id}")
async def deregister_worker(
    worker_id: str,
    force: bool = False,
    db: Session = Depends(get_db),
    current_user_dict: dict = Depends(get_current_user),
):
    """Deregister a worker with graceful shutdown"""

    current_user = UserInfo(**current_user_dict)

    # Only admins or workers themselves can deregister
    if current_user.role not in ["system_admin", "tenant_admin", "worker"]:
        raise HTTPException(
            status_code=403, detail="Only admins or workers can deregister workers"
        )

    worker = (
        db.query(Worker)
        .filter(
            and_(
                Worker.worker_id == worker_id,
                Worker.tenant_id == current_user.tenant_id,
            )
        )
        .first()
    )

    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")

    # Check if worker is online and should be gracefully shutdown
    if (
        not force
        and worker.status in ["idle", "processing", "online"]
        and is_worker_healthy(worker)
    ):
        # Request graceful shutdown first
        try:
            shutdown_result = await worker_shutdown_service.request_worker_shutdown(
                worker_id=worker_id,
                signal=ShutdownSignal.GRACEFUL,
                timeout=30,
                requested_by=current_user.sub,
            )

            if shutdown_result["success"]:
                return {
                    "message": "Graceful shutdown requested for worker. Worker will be deregistered after shutdown.",
                    "shutdown_requested": True,
                    "shutdown_timeout": 30,
                    "worker_name": worker.worker_name,
                }
        except Exception as e:
            logger.warning(
                f"Failed to request graceful shutdown for worker {worker_id}: {e}"
            )

    # Force delete if:
    # 1. force=True parameter
    # 2. Worker is already offline
    # 3. Graceful shutdown failed
    logger.info(f"Force deleting worker {worker_id} ({worker.worker_name})")

    # Broadcast worker deletion before removing from database
    worker.status = "offline"
    await broadcast_worker_status_update(worker, current_user.tenant_id)

    db.delete(worker)
    db.commit()

    # Broadcast list refresh to update frontend
    await connection_manager.broadcast_worker_list_update(current_user.tenant_id)

    return {
        "message": "Worker deregistered successfully",
        "shutdown_requested": False,
        "force_deleted": True,
    }


@router.post("/workers/cleanup-stale")
async def cleanup_stale_workers(
    minutes_threshold: int = 5,
    db: Session = Depends(get_db),
    current_user_dict: dict = Depends(get_current_user),
):
    """Cleanup workers that haven't sent heartbeat for specified minutes"""

    current_user = UserInfo(**current_user_dict)

    # Only admins can cleanup stale workers
    if current_user.role not in ["system_admin", "tenant_admin"]:
        raise HTTPException(
            status_code=403, detail="Only admins can cleanup stale workers"
        )

    threshold_time = datetime.utcnow() - timedelta(minutes=minutes_threshold)

    # Update workers to offline status if they haven't sent heartbeat
    stale_workers = (
        db.query(Worker)
        .filter(
            and_(
                Worker.tenant_id == current_user.tenant_id,
                Worker.status.in_(["idle", "processing", "online"]),
                Worker.last_heartbeat < threshold_time,
            )
        )
        .all()
    )

    updated_count = 0
    for worker in stale_workers:
        worker.status = "offline"
        worker.camera_id = None  # Release camera assignment
        worker.updated_at = datetime.utcnow()
        updated_count += 1

    db.commit()

    return {
        "message": f"Updated {updated_count} stale workers to offline status",
        "threshold_minutes": minutes_threshold,
        "updated_count": updated_count,
    }


@router.post("/workers/force-cleanup")
async def force_worker_cleanup(
    current_user_dict: dict = Depends(get_current_user),
):
    """Force cleanup of stale workers using the monitoring service"""

    current_user = UserInfo(**current_user_dict)

    # Only system admins can force cleanup
    if current_user.role != "system_admin":
        raise HTTPException(
            status_code=403, detail="Only system admins can force worker cleanup"
        )

    try:
        # Import here to avoid circular imports
        from ..services.worker_monitor_service import worker_monitor_service

        updated_count = await worker_monitor_service.cleanup_stale_workers(
            minutes_threshold=1
        )

        return {
            "message": f"Force cleaned up {updated_count} stale workers",
            "updated_count": updated_count,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to force cleanup workers: {str(e)}"
        )


@router.post("/workers/{worker_id}/shutdown", response_model=WorkerShutdownResponse)
async def shutdown_worker(
    worker_id: str,
    shutdown_request: WorkerShutdownRequest,
    db: Session = Depends(get_db),
    current_user_dict: dict = Depends(get_current_user),
):
    """Request worker to shutdown gracefully"""

    current_user = UserInfo(**current_user_dict)

    # Only admins can shutdown workers
    if current_user.role not in ["system_admin", "tenant_admin"]:
        raise HTTPException(status_code=403, detail="Only admins can shutdown workers")

    # Validate worker exists and belongs to tenant
    worker = (
        db.query(Worker)
        .filter(
            and_(
                Worker.worker_id == worker_id,
                Worker.tenant_id == current_user.tenant_id,
            )
        )
        .first()
    )

    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")

    # Validate shutdown signal
    try:
        signal = ShutdownSignal(shutdown_request.signal)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid shutdown signal. Use: graceful, immediate, or restart",
        )

    # Request shutdown
    result = await worker_shutdown_service.request_worker_shutdown(
        worker_id=worker_id,
        signal=signal,
        timeout=shutdown_request.timeout,
        requested_by=current_user.sub,
    )

    if result["success"]:
        return WorkerShutdownResponse(**result)
    else:
        raise HTTPException(
            status_code=500,
            detail=result.get("error", "Failed to request worker shutdown"),
        )


class WorkerStopSignalRequest(BaseModel):
    worker_id: str = Field(..., description="Worker ID sending stop signal")
    reason: str = Field(
        default="shutdown_requested", description="Reason for stop signal"
    )
    timestamp: str = Field(..., description="Timestamp when signal was sent")


@router.post("/workers/{worker_id}/stop-signal")
async def receive_worker_stop_signal(
    worker_id: str,
    stop_signal: WorkerStopSignalRequest,
    db: Session = Depends(get_db),
    current_user_dict: dict = Depends(get_current_user),
):
    """
    Receive stop signal from worker (sent during shutdown process)

    This endpoint:
    1. Acknowledges receipt of shutdown signal from worker
    2. Triggers backend cleanup tasks
    3. Releases camera assignments
    4. Updates worker status
    5. Broadcasts status updates
    """

    current_user = UserInfo(**current_user_dict)

    # Only workers can send stop signals
    if current_user.role not in ["worker", "system_admin"]:
        raise HTTPException(
            status_code=403,
            detail="Only workers or system admins can send stop signals",
        )

    # Find worker
    worker = (
        db.query(Worker)
        .filter(
            and_(
                Worker.worker_id == worker_id,
                Worker.tenant_id == current_user.tenant_id,
            )
        )
        .first()
    )

    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")

    # Log the stop signal reception
    logger.info(
        f"✅ Received stop signal from worker {worker_id} ({worker.worker_name}): {stop_signal.reason}"
    )

    # 1. Release camera assignment immediately
    assigned_camera_id = worker.camera_id
    if assigned_camera_id:
        logger.info(
            f"🔓 Releasing camera {assigned_camera_id} from shutting down worker {worker_id}"
        )
        worker.camera_id = None

        # Also trigger cleanup in camera delegation service
        try:
            from ..services.camera_delegation_service import camera_delegation_service

            camera_delegation_service.release_camera_from_worker(worker_id)
            logger.info(
                f"✅ Camera {assigned_camera_id} released via delegation service"
            )
        except Exception as e:
            logger.error(f"❌ Error releasing camera via delegation service: {e}")

    # 2. Update worker status and clear from registries
    worker.status = "offline"
    worker.last_error = f"Worker shutdown: {stop_signal.reason}"
    worker.last_heartbeat = datetime.utcnow()  # Mark final heartbeat
    worker.updated_at = datetime.utcnow()

    # 3. Clean up from worker registry if present
    try:
        from ..services.worker_registry import worker_registry

        if worker_registry.get_worker(worker_id):
            await worker_registry.remove_worker(worker_id)
            logger.info(f"✅ Worker {worker_id} removed from worker registry")
    except Exception as e:
        logger.error(f"❌ Error removing worker from registry: {e}")

    # 4. Update database
    db.commit()
    db.refresh(worker)

    # 5. Broadcast worker status update to frontend
    try:
        await broadcast_worker_status_update(worker, current_user.tenant_id)
        logger.info(f"📢 Broadcasted worker shutdown status for {worker_id}")
    except Exception as e:
        logger.error(f"❌ Error broadcasting worker stop signal update: {e}")

    # 6. Log successful cleanup completion
    logger.info(f"🎉 Worker {worker_id} shutdown cleanup completed successfully")

    # 7. Return acknowledgment to worker
    return {
        "message": "Stop signal received and acknowledged - backend cleanup completed",
        "worker_id": worker_id,
        "status": "acknowledged_and_cleaned",
        "camera_released": assigned_camera_id is not None,
        "released_camera_id": assigned_camera_id,
        "backend_cleanup_completed": True,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.post("/workers/{worker_id}/shutdown-signal")
async def get_shutdown_signal(
    worker_id: str,
    current_user_dict: dict = Depends(get_current_user),
):
    """Get pending shutdown signal for worker (called by worker during heartbeat)"""

    current_user = UserInfo(**current_user_dict)

    # Only workers and admins can check shutdown signals
    if current_user.role not in ["worker", "system_admin"]:
        raise HTTPException(
            status_code=403,
            detail="Only workers or system admins can check shutdown signals",
        )

    signal = await worker_shutdown_service.get_shutdown_signal(worker_id)

    return {"has_shutdown_signal": signal is not None, "shutdown_signal": signal}


@router.post("/workers/{worker_id}/acknowledge-shutdown")
async def acknowledge_shutdown(
    worker_id: str,
    current_user_dict: dict = Depends(get_current_user),
):
    """Acknowledge receipt of shutdown signal (called by worker)"""

    current_user = UserInfo(**current_user_dict)

    # Only workers can acknowledge shutdown
    if current_user.role not in ["worker", "system_admin"]:
        raise HTTPException(
            status_code=403,
            detail="Only workers or system admins can acknowledge shutdown",
        )

    success = await worker_shutdown_service.acknowledge_shutdown(worker_id)

    if success:
        return {"message": "Shutdown acknowledged"}
    else:
        raise HTTPException(status_code=404, detail="No pending shutdown found")


@router.post("/workers/{worker_id}/complete-shutdown")
async def complete_shutdown(
    worker_id: str,
    current_user_dict: dict = Depends(get_current_user),
):
    """Mark worker shutdown as completed (called by worker before exit)"""

    current_user = UserInfo(**current_user_dict)

    # Only workers can complete shutdown
    if current_user.role not in ["worker", "system_admin"]:
        raise HTTPException(
            status_code=403,
            detail="Only workers or system admins can complete shutdown",
        )

    success = await worker_shutdown_service.complete_shutdown(worker_id)

    if success:
        return {"message": "Shutdown completed"}
    else:
        raise HTTPException(status_code=404, detail="No pending shutdown found")


@router.get("/workers/shutdown-status")
async def get_shutdown_status(
    current_user_dict: dict = Depends(get_current_user),
):
    """Get status of all pending shutdowns (admin only)"""

    current_user = UserInfo(**current_user_dict)

    # Only admins can see shutdown status
    if current_user.role not in ["system_admin", "tenant_admin"]:
        raise HTTPException(
            status_code=403, detail="Only admins can view shutdown status"
        )

    pending_shutdowns = worker_shutdown_service.get_pending_shutdowns()

    return {
        "pending_shutdowns": list(pending_shutdowns.values()),
        "total_pending": len(pending_shutdowns),
    }


@router.websocket("/workers/ws/{tenant_id}")
async def websocket_endpoint(
    websocket: WebSocket, tenant_id: str, token: Optional[str] = None
):
    """WebSocket endpoint for real-time worker status updates"""
    try:
        await connection_manager.connect(websocket, tenant_id)

        # Send initial worker status
        try:
            async with get_db_session() as db:
                result = await db.execute(
                    select(Worker).where(Worker.tenant_id == tenant_id)
                )
                workers = result.scalars().all()

            initial_data = []
            for worker in workers:
                capabilities = None
                if worker.capabilities:
                    try:
                        capabilities = json.loads(worker.capabilities)
                    except json.JSONDecodeError:
                        capabilities = None

                initial_data.append(
                    {
                        "worker_id": worker.worker_id,
                        "tenant_id": worker.tenant_id,
                        "hostname": worker.hostname,
                        "ip_address": worker.ip_address,
                        "worker_name": worker.worker_name,
                        "worker_version": worker.worker_version,
                        "capabilities": capabilities,
                        "status": worker.status,
                        "site_id": worker.site_id,
                        "camera_id": worker.camera_id,
                        "last_heartbeat": (
                            worker.last_heartbeat.isoformat()
                            if worker.last_heartbeat
                            else None
                        ),
                        "last_error": worker.last_error,
                        "error_count": worker.error_count,
                        "total_faces_processed": worker.total_faces_processed,
                        "uptime_minutes": calculate_uptime_minutes(worker),
                        "registration_time": worker.registration_time.isoformat(),
                        "is_healthy": is_worker_healthy(worker),
                    }
                )

            await websocket.send_json(
                {
                    "type": "initial_data",
                    "data": initial_data,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )

        except Exception as e:
            print(f"Error sending initial data: {e}")

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


# Worker Management Commands - moved from missing worker_management router


@router.get("/worker-management/commands/{worker_id}/pending")
async def get_pending_commands(
    worker_id: str,
    limit: int = 10,
    current_user_dict: dict = Depends(get_current_user),
):
    """Get pending commands for a worker"""

    current_user = UserInfo(**current_user_dict)

    # Only workers and admins can check pending commands
    if current_user.role not in ["worker", "system_admin"]:
        raise HTTPException(
            status_code=403,
            detail="Only workers or system admins can check pending commands",
        )

    try:
        # Import command service here to avoid circular imports
        from ..services.worker_command_service import worker_command_service

        commands = worker_command_service.get_pending_commands(worker_id, limit=limit)

        return {
            "worker_id": worker_id,
            "pending_commands": commands,
            "count": len(commands),
        }

    except Exception as e:
        logger.error(f"Error getting pending commands for worker {worker_id}: {e}")
        return {"worker_id": worker_id, "pending_commands": [], "count": 0}


@router.post("/worker-management/commands/{command_id}/acknowledge")
async def acknowledge_command(
    command_id: str,
    worker_id: str,
    current_user_dict: dict = Depends(get_current_user),
):
    """Acknowledge receipt of a command"""

    current_user = UserInfo(**current_user_dict)

    # Only workers can acknowledge commands
    if current_user.role not in ["worker", "system_admin"]:
        raise HTTPException(
            status_code=403,
            detail="Only workers or system admins can acknowledge commands",
        )

    try:
        from ..services.worker_command_service import worker_command_service

        success = worker_command_service.acknowledge_command(command_id, worker_id)

        if success:
            return {"message": "Command acknowledged"}
        else:
            raise HTTPException(status_code=404, detail="Command not found")

    except Exception as e:
        logger.error(f"Error acknowledging command {command_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to acknowledge command")


@router.post("/worker-management/commands/{command_id}/complete")
async def complete_command(
    command_id: str,
    completion_data: dict,
    current_user_dict: dict = Depends(get_current_user),
):
    """Mark a command as completed with optional result data"""

    current_user = UserInfo(**current_user_dict)

    # Only workers can complete commands
    if current_user.role not in ["worker", "system_admin"]:
        raise HTTPException(
            status_code=403,
            detail="Only workers or system admins can complete commands",
        )

    worker_id = completion_data.get("worker_id")
    result = completion_data.get("result")
    error_message = completion_data.get("error_message")

    if not worker_id:
        raise HTTPException(status_code=400, detail="worker_id is required")

    try:
        from ..services.worker_command_service import worker_command_service

        success = worker_command_service.complete_command(
            command_id=command_id,
            worker_id=worker_id,
            result=result,
            error_message=error_message,
        )

        if success:
            return {"message": "Command completed"}
        else:
            raise HTTPException(status_code=404, detail="Command not found")

    except Exception as e:
        logger.error(f"Error completing command {command_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to complete command")
