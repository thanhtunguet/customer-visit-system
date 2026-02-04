from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from common.enums.commands import CommandPriority, WorkerCommand
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db_session
from ..core.security import get_current_user, get_current_user_for_stream
from ..services.camera_delegation_service import camera_delegation_service
from ..services.worker_command_service import worker_command_service
from ..services.worker_registry import worker_registry

logger = logging.getLogger(__name__)


class UserInfo(BaseModel):
    sub: str
    role: str
    tenant_id: str


class CameraAssignmentRequest(BaseModel):
    worker_id: str = Field(..., description="ID of worker to assign camera to")
    site_id: int = Field(..., description="Site ID where camera should be assigned")


class CameraAssignmentResponse(BaseModel):
    success: bool
    message: str
    worker_id: str
    camera_id: Optional[int] = None
    camera_name: Optional[str] = None


class WorkerCommandRequest(BaseModel):
    command: str = Field(..., description="Command to send to worker")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Command parameters")
    priority: str = Field(
        "normal", description="Command priority: low, normal, high, urgent"
    )
    timeout_minutes: Optional[int] = Field(
        None, description="Command timeout in minutes"
    )


class WorkerCommandResponse(BaseModel):
    success: bool
    message: str
    command_id: str
    expires_at: str


class AssignmentStatusResponse(BaseModel):
    camera_id: int
    worker_id: str
    worker_name: str
    worker_status: str
    is_healthy: bool
    site_id: int
    assigned_at: str


class AssignmentsListResponse(BaseModel):
    assignments: Dict[str, AssignmentStatusResponse]
    total_assignments: int
    active_assignments: int
    stale_assignments: int


router = APIRouter(prefix="/v1/worker-management", tags=["worker-camera-management"])


@router.post("/assign-camera", response_model=CameraAssignmentResponse)
async def assign_camera_to_worker(
    request: CameraAssignmentRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user_dict: dict = Depends(get_current_user),
):
    """Assign an available camera to a worker"""

    current_user = UserInfo(**current_user_dict)

    # Only admins can assign cameras
    if current_user.role not in ["system_admin", "tenant_admin", "site_manager"]:
        raise HTTPException(
            status_code=403, detail="Only admins can assign cameras to workers"
        )

    # Check if worker exists in registry
    worker = worker_registry.get_worker(request.worker_id)
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")

    # Verify worker belongs to current tenant
    if worker.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=403, detail="Worker belongs to different tenant"
        )

    # Assign camera
    try:
        camera = await camera_delegation_service.assign_camera_to_worker(
            db=db,
            tenant_id=current_user.tenant_id,
            worker_id=request.worker_id,
            site_id=request.site_id,
        )

        if camera:
            # Send command to worker to start processing
            worker_command_service.send_command(
                worker_id=request.worker_id,
                command=WorkerCommand.ASSIGN_CAMERA,
                parameters={
                    "camera_id": camera.camera_id,
                    "camera_name": camera.name,
                    "rtsp_url": camera.rtsp_url,
                    "device_index": camera.device_index,
                    "camera_type": (
                        camera.camera_type.value if camera.camera_type else "webcam"
                    ),
                },
                priority=CommandPriority.HIGH,
                requested_by=current_user.sub,
            )

            return CameraAssignmentResponse(
                success=True,
                message=f"Camera {camera.camera_id} assigned to worker {worker.worker_name}",
                worker_id=request.worker_id,
                camera_id=camera.camera_id,
                camera_name=camera.name,
            )
        else:
            return CameraAssignmentResponse(
                success=False,
                message=f"No available cameras in site {request.site_id}",
                worker_id=request.worker_id,
            )

    except Exception as e:
        logger.error(f"Error assigning camera: {e}")
        raise HTTPException(status_code=500, detail="Failed to assign camera")


@router.post("/release-camera/{worker_id}")
async def release_camera_from_worker(
    worker_id: str,
    current_user_dict: dict = Depends(get_current_user),
):
    """Release camera assignment from a worker"""

    current_user = UserInfo(**current_user_dict)

    # Only admins can release cameras
    if current_user.role not in ["system_admin", "tenant_admin", "site_manager"]:
        raise HTTPException(
            status_code=403, detail="Only admins can release cameras from workers"
        )

    # Check if worker exists in registry
    worker = worker_registry.get_worker(worker_id)
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")

    # Verify worker belongs to current tenant
    if worker.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=403, detail="Worker belongs to different tenant"
        )

    # Release camera
    try:
        camera_id = camera_delegation_service.release_camera_from_worker(worker_id)

        if camera_id:
            # Send command to worker to stop processing
            worker_command_service.send_command(
                worker_id=worker_id,
                command=WorkerCommand.RELEASE_CAMERA,
                priority=CommandPriority.HIGH,
                requested_by=current_user.sub,
            )

            return {
                "success": True,
                "message": f"Camera {camera_id} released from worker {worker.worker_name}",
                "camera_id": camera_id,
            }
        else:
            return {
                "success": False,
                "message": f"Worker {worker.worker_name} has no camera assigned",
            }

    except Exception as e:
        logger.error(f"Error releasing camera: {e}")
        raise HTTPException(status_code=500, detail="Failed to release camera")


@router.post("/send-command/{worker_id}", response_model=WorkerCommandResponse)
async def send_command_to_worker(
    worker_id: str,
    request: WorkerCommandRequest,
    current_user_dict: dict = Depends(get_current_user),
):
    """Send a command to a worker"""

    current_user = UserInfo(**current_user_dict)

    # Only admins can send commands
    if current_user.role not in ["system_admin", "tenant_admin", "site_manager"]:
        raise HTTPException(
            status_code=403, detail="Only admins can send commands to workers"
        )

    # Check if worker exists in registry
    worker = worker_registry.get_worker(worker_id)
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")

    # Verify worker belongs to current tenant
    if worker.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=403, detail="Worker belongs to different tenant"
        )

    # Validate command
    try:
        command = WorkerCommand.from_string(request.command)
    except ValueError:
        raise HTTPException(
            status_code=400, detail=f"Invalid command: {request.command}"
        )

    # Validate priority
    try:
        priority = CommandPriority[request.priority.upper()]
    except KeyError:
        raise HTTPException(
            status_code=400, detail=f"Invalid priority: {request.priority}"
        )

    # Send command
    try:
        command_id = worker_command_service.send_command(
            worker_id=worker_id,
            command=command,
            parameters=request.parameters,
            priority=priority,
            requested_by=current_user.sub,
            timeout_minutes=request.timeout_minutes,
        )

        # Get command details for response
        command_msg = worker_command_service.get_command_status(command_id)

        return WorkerCommandResponse(
            success=True,
            message=f"Command {command.value} sent to worker {worker.worker_name}",
            command_id=command_id,
            expires_at=command_msg.expires_at.isoformat() if command_msg else "",
        )

    except Exception as e:
        logger.error(f"Error sending command: {e}")
        raise HTTPException(status_code=500, detail="Failed to send command")


@router.get("/assignments", response_model=AssignmentsListResponse)
async def list_camera_assignments(
    current_user_dict: dict = Depends(get_current_user),
):
    """List all current camera-worker assignments"""

    current_user = UserInfo(**current_user_dict)

    # Get assignments for current tenant
    assignments = camera_delegation_service.list_assignments(
        tenant_id=current_user.tenant_id
    )

    # Convert to response format
    assignment_responses = {}
    active_count = 0
    stale_count = 0

    for camera_id_str, assignment in assignments.items():
        assignment_responses[camera_id_str] = AssignmentStatusResponse(
            camera_id=assignment["camera_id"],
            worker_id=assignment["worker_id"],
            worker_name=assignment["worker_name"],
            worker_status=assignment["worker_status"],
            is_healthy=assignment["is_healthy"],
            site_id=assignment["site_id"],
            assigned_at=assignment["assigned_at"],
        )

        if assignment["is_healthy"]:
            active_count += 1
        else:
            stale_count += 1

    return AssignmentsListResponse(
        assignments=assignment_responses,
        total_assignments=len(assignments),
        active_assignments=active_count,
        stale_assignments=stale_count,
    )


@router.post("/assignments/cleanup")
async def cleanup_stale_assignments(
    current_user_dict: dict = Depends(get_current_user),
):
    """Clean up stale camera assignments"""

    current_user = UserInfo(**current_user_dict)

    # Only admins can cleanup assignments
    if current_user.role not in ["system_admin", "tenant_admin"]:
        raise HTTPException(
            status_code=403, detail="Only admins can cleanup stale assignments"
        )

    try:
        cleaned_count = camera_delegation_service.cleanup_stale_assignments()

        return {
            "message": f"Cleaned up {cleaned_count} stale assignments",
            "cleaned_count": cleaned_count,
        }

    except Exception as e:
        logger.error(f"Error cleaning up assignments: {e}")
        raise HTTPException(status_code=500, detail="Failed to cleanup assignments")


@router.post("/assignments/auto-assign")
async def auto_assign_cameras(
    db: AsyncSession = Depends(get_db_session),
    current_user_dict: dict = Depends(get_current_user),
):
    """Automatically assign cameras to idle workers"""

    current_user = UserInfo(**current_user_dict)

    # Only admins can trigger auto-assignment
    if current_user.role not in ["system_admin", "tenant_admin"]:
        raise HTTPException(
            status_code=403, detail="Only admins can trigger auto-assignment"
        )

    try:
        assigned_count = await camera_delegation_service.reassign_cameras_automatically(
            db=db, tenant_id=current_user.tenant_id
        )

        return {
            "message": f"Automatically assigned {assigned_count} cameras to idle workers",
            "assigned_count": assigned_count,
        }

    except Exception as e:
        logger.error(f"Error in auto-assignment: {e}")
        raise HTTPException(status_code=500, detail="Failed to auto-assign cameras")


@router.get("/commands/{worker_id}")
async def get_worker_commands(
    worker_id: str,
    include_history: bool = False,
    current_user_dict: dict = Depends(get_current_user),
):
    """Get commands for a worker"""

    current_user = UserInfo(**current_user_dict)

    # Check if worker exists in registry
    worker = worker_registry.get_worker(worker_id)
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")

    # Verify worker belongs to current tenant
    if worker.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=403, detail="Worker belongs to different tenant"
        )

    try:
        commands = worker_command_service.get_worker_commands(
            worker_id=worker_id, include_history=include_history
        )

        return {
            "worker_id": worker_id,
            "worker_name": worker.worker_name,
            "commands": [cmd.to_dict() for cmd in commands],
        }

    except Exception as e:
        logger.error(f"Error getting worker commands: {e}")
        raise HTTPException(status_code=500, detail="Failed to get worker commands")


@router.get("/commands/{worker_id}/pending")
async def get_pending_commands_for_worker(
    worker_id: str,
    limit: int = 10,
    current_user_dict: dict = Depends(get_current_user),
):
    """Get pending commands for a worker (called by worker client)"""

    current_user = UserInfo(**current_user_dict)

    # Only workers or admins can get pending commands
    if current_user.role not in ["worker", "system_admin"]:
        raise HTTPException(
            status_code=403, detail="Only workers or admins can get pending commands"
        )

    # Check if worker exists in registry
    worker = worker_registry.get_worker(worker_id)
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")

    # Verify worker belongs to current tenant
    if worker.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=403, detail="Worker belongs to different tenant"
        )

    try:
        commands = worker_command_service.get_pending_commands(worker_id, limit=limit)

        return {
            "worker_id": worker_id,
            "pending_commands": [cmd.to_dict() for cmd in commands],
        }

    except Exception as e:
        logger.error(f"Error getting pending commands: {e}")
        raise HTTPException(status_code=500, detail="Failed to get pending commands")


@router.post("/commands/{command_id}/acknowledge")
async def acknowledge_command(
    command_id: str,
    worker_id: str,
    current_user_dict: dict = Depends(get_current_user),
):
    """Acknowledge command receipt (called by worker client)"""

    current_user = UserInfo(**current_user_dict)

    # Only workers can acknowledge commands
    if current_user.role not in ["worker", "system_admin"]:
        raise HTTPException(
            status_code=403, detail="Only workers can acknowledge commands"
        )

    try:
        success = worker_command_service.acknowledge_command(command_id, worker_id)

        if success:
            return {"message": "Command acknowledged", "command_id": command_id}
        else:
            raise HTTPException(status_code=404, detail="Command not found or expired")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error acknowledging command: {e}")
        raise HTTPException(status_code=500, detail="Failed to acknowledge command")


@router.post("/commands/{command_id}/complete")
async def complete_command(
    command_id: str,
    worker_id: str,
    result: Optional[Dict[str, Any]] = None,
    error_message: Optional[str] = None,
    current_user_dict: dict = Depends(get_current_user),
):
    """Mark command as completed (called by worker client)"""

    current_user = UserInfo(**current_user_dict)

    # Only workers can complete commands
    if current_user.role not in ["worker", "system_admin"]:
        raise HTTPException(
            status_code=403, detail="Only workers can complete commands"
        )

    try:
        success = worker_command_service.complete_command(
            command_id=command_id,
            worker_id=worker_id,
            result=result,
            error_message=error_message,
        )

        if success:
            return {
                "message": "Command completed",
                "command_id": command_id,
                "success": error_message is None,
            }
        else:
            raise HTTPException(status_code=404, detail="Command not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error completing command: {e}")
        raise HTTPException(status_code=500, detail="Failed to complete command")


@router.delete("/commands/{command_id}")
async def cancel_command(
    command_id: str,
    reason: str = "Cancelled by admin",
    current_user_dict: dict = Depends(get_current_user),
):
    """Cancel a pending command"""

    current_user = UserInfo(**current_user_dict)

    # Only admins can cancel commands
    if current_user.role not in ["system_admin", "tenant_admin"]:
        raise HTTPException(status_code=403, detail="Only admins can cancel commands")

    try:
        success = worker_command_service.cancel_command(command_id, reason)

        if success:
            return {
                "message": "Command cancelled",
                "command_id": command_id,
                "reason": reason,
            }
        else:
            raise HTTPException(status_code=404, detail="Command not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling command: {e}")
        raise HTTPException(status_code=500, detail="Failed to cancel command")


@router.get("/workers/{worker_id}/logs/recent")
async def get_worker_recent_logs(
    worker_id: str,
    limit: int = 100,
    current_user_dict: dict = Depends(get_current_user),
):
    """Get recent log entries from a worker"""
    import httpx

    current_user = UserInfo(**current_user_dict)

    # Only admins and the worker itself can access logs
    if (
        current_user.role not in ["system_admin", "tenant_admin"]
        and current_user.sub != "worker"
    ):
        raise HTTPException(
            status_code=403, detail="Only admins or workers can access logs"
        )

    try:
        # Get worker info to find its HTTP endpoint
        worker_info = worker_registry.get_worker(worker_id)
        if not worker_info:
            raise HTTPException(status_code=404, detail="Worker not found")

        # Check if worker is online and has HTTP server
        if not worker_info.is_healthy or not worker_info.ip_address:
            raise HTTPException(status_code=503, detail="Worker is not available")

        # Get worker HTTP port (default 8090)
        worker_port = 8090  # Could be configurable per worker
        worker_url = f"http://{worker_info.ip_address}:{worker_port}"

        # Proxy request to worker
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{worker_url}/logs/recent", params={"limit": limit}
            )
            response.raise_for_status()

            return response.json()

    except httpx.RequestError as e:
        logger.error(f"Error connecting to worker {worker_id}: {e}")
        raise HTTPException(status_code=503, detail="Unable to connect to worker")
    except httpx.HTTPStatusError as e:
        logger.error(f"Worker {worker_id} returned error: {e}")
        raise HTTPException(
            status_code=e.response.status_code, detail="Worker request failed"
        )
    except Exception as e:
        logger.error(f"Error fetching logs from worker {worker_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch worker logs")


@router.get("/workers/{worker_id}/logs/stream")
async def stream_worker_logs(
    worker_id: str,
    request: Request,
    token: str = Query(None),
    current_user_dict: dict = Depends(get_current_user_for_stream),
):
    """Stream real-time logs from a worker via Server-Sent Events"""
    import httpx
    from fastapi.responses import StreamingResponse

    current_user = UserInfo(**current_user_dict)

    # Only admins and the worker itself can access logs
    if (
        current_user.role not in ["system_admin", "tenant_admin"]
        and current_user.sub != "worker"
    ):
        raise HTTPException(
            status_code=403, detail="Only admins or workers can access logs"
        )

    try:
        # Get worker info to find its HTTP endpoint
        worker_info = worker_registry.get_worker(worker_id)
        if not worker_info:
            raise HTTPException(status_code=404, detail="Worker not found")

        if not worker_info.is_healthy or not worker_info.ip_address:
            raise HTTPException(status_code=503, detail="Worker is not available")

        worker_port = 8090
        worker_url = f"http://{worker_info.ip_address}:{worker_port}"

        # Stream proxy to worker's log stream
        async def log_proxy_generator():
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    async with client.stream(
                        "GET", f"{worker_url}/logs/stream"
                    ) as response:
                        response.raise_for_status()

                        async for chunk in response.aiter_text():
                            # Check if client disconnected
                            if await request.is_disconnected():
                                break
                            yield chunk

            except httpx.RequestError as e:
                logger.error(f"Error streaming from worker {worker_id}: {e}")
                yield "event: error\ndata: Unable to connect to worker\n\n"
            except Exception as e:
                logger.error(f"Error in log stream proxy: {e}")
                yield "event: error\ndata: Stream connection lost\n\n"

        return StreamingResponse(
            log_proxy_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Cache-Control",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting up log stream for worker {worker_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to setup log stream")


@router.post("/workers/{worker_id}/logs/test")
async def trigger_worker_test_logs(
    worker_id: str,
    current_user_dict: dict = Depends(get_current_user),
):
    """Trigger test log generation on worker (for testing)"""
    import httpx

    current_user = UserInfo(**current_user_dict)

    if current_user.role not in ["system_admin", "tenant_admin"]:
        raise HTTPException(status_code=403, detail="Only admins can trigger test logs")

    try:
        worker_info = worker_registry.get_worker(worker_id)
        if not worker_info:
            raise HTTPException(status_code=404, detail="Worker not found")

        if not worker_info.is_healthy or not worker_info.ip_address:
            raise HTTPException(status_code=503, detail="Worker is not available")

        worker_port = 8090
        worker_url = f"http://{worker_info.ip_address}:{worker_port}"

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(f"{worker_url}/logs/test")
            response.raise_for_status()

            return response.json()

    except httpx.RequestError as e:
        logger.error(f"Error connecting to worker {worker_id}: {e}")
        raise HTTPException(status_code=503, detail="Unable to connect to worker")
    except Exception as e:
        logger.error(f"Error triggering test logs: {e}")
        raise HTTPException(status_code=500, detail="Failed to trigger test logs")
