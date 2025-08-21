import logging
from typing import List, Dict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db_session, db
from ..core.security import get_current_user, get_current_user_for_stream
from ..models.database import Camera
from ..schemas import CameraCreate, CameraResponse
from ..services.camera_streaming_service import streaming_service
from ..services.camera_diagnostics import camera_diagnostics

router = APIRouter(prefix="/v1", tags=["Camera Management"])
logger = logging.getLogger(__name__)


@router.get("/sites/{site_id}/cameras", response_model=List[CameraResponse])
async def list_cameras(
    site_id: str,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    await db.set_tenant_context(db_session, user["tenant_id"])
    
    result = await db_session.execute(
        select(Camera).where(
            and_(Camera.tenant_id == user["tenant_id"], Camera.site_id == site_id)
        )
    )
    cameras = result.scalars().all()
    return cameras


@router.post("/sites/{site_id}/cameras", response_model=CameraResponse)
async def create_camera(
    site_id: str,
    camera: CameraCreate,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    await db.set_tenant_context(db_session, user["tenant_id"])
    
    # Generate camera ID
    import uuid
    camera_id = f"cam-{uuid.uuid4().hex[:8]}"
    
    new_camera = Camera(
        tenant_id=user["tenant_id"],
        site_id=site_id,
        camera_id=camera_id,
        name=camera.name,
        camera_type=camera.camera_type,
        rtsp_url=camera.rtsp_url,
        device_index=camera.device_index
    )
    db_session.add(new_camera)
    await db_session.commit()
    return new_camera


@router.get("/sites/{site_id}/cameras/{camera_id}", response_model=CameraResponse)
async def get_camera(
    site_id: str,
    camera_id: str,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    await db.set_tenant_context(db_session, user["tenant_id"])
    
    result = await db_session.execute(
        select(Camera).where(
            and_(
                Camera.tenant_id == user["tenant_id"],
                Camera.site_id == site_id,
                Camera.camera_id == camera_id
            )
        )
    )
    camera = result.scalar_one_or_none()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    return camera


@router.put("/sites/{site_id}/cameras/{camera_id}", response_model=CameraResponse)
async def update_camera(
    site_id: str,
    camera_id: str,
    camera_update: CameraCreate,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    await db.set_tenant_context(db_session, user["tenant_id"])
    
    result = await db_session.execute(
        select(Camera).where(
            and_(
                Camera.tenant_id == user["tenant_id"],
                Camera.site_id == site_id,
                Camera.camera_id == camera_id
            )
        )
    )
    camera = result.scalar_one_or_none()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    # Update camera fields
    camera.name = camera_update.name
    camera.camera_type = camera_update.camera_type
    camera.rtsp_url = camera_update.rtsp_url
    camera.device_index = camera_update.device_index
    
    await db_session.commit()
    await db_session.refresh(camera)
    return camera


@router.delete("/sites/{site_id}/cameras/{camera_id}")
async def delete_camera(
    site_id: str,
    camera_id: str,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    await db.set_tenant_context(db_session, user["tenant_id"])
    
    result = await db_session.execute(
        select(Camera).where(
            and_(
                Camera.tenant_id == user["tenant_id"],
                Camera.site_id == site_id,
                Camera.camera_id == camera_id
            )
        )
    )
    camera = result.scalar_one_or_none()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    await db_session.delete(camera)
    await db_session.commit()
    return {"message": "Camera deleted successfully"}


# Camera Streaming Endpoints

@router.post("/sites/{site_id}/cameras/{camera_id}/stream/start")
async def start_camera_stream(
    site_id: str,
    camera_id: str,
    user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    """Start streaming for a specific camera"""
    tenant_id = user["tenant_id"]
    
    # Debug logging
    logger.info(f"Starting camera stream - tenant_id: {tenant_id} (type: {type(tenant_id)}), site_id: {site_id} (type: {type(site_id)}), camera_id: {camera_id} (type: {type(camera_id)})")
    
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Invalid tenant_id from token")
    
    await db.set_tenant_context(db_session, str(tenant_id))
    
    # Get camera info
    result = await db_session.execute(
        select(Camera).where(
            and_(
                Camera.tenant_id == tenant_id,
                Camera.site_id == site_id,
                Camera.camera_id == camera_id
            )
        )
    )
    camera = result.scalar_one_or_none()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    if not camera.is_active:
        raise HTTPException(status_code=400, detail="Camera is not active")
    
    # Start streaming
    success = streaming_service.start_stream(
        camera_id=camera_id,
        camera_type=camera.camera_type.value,
        rtsp_url=camera.rtsp_url,
        device_index=camera.device_index
    )
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to start camera stream")
    
    return {
        "message": "Camera stream started successfully",
        "camera_id": camera_id,
        "stream_active": True
    }


@router.post("/sites/{site_id}/cameras/{camera_id}/stream/stop")
async def stop_camera_stream(
    site_id: str,
    camera_id: str,
    user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    """Stop streaming for a specific camera"""
    tenant_id = user["tenant_id"]
    await db.set_tenant_context(db_session, tenant_id)
    
    # Verify camera exists
    result = await db_session.execute(
        select(Camera).where(
            and_(
                Camera.tenant_id == tenant_id,
                Camera.site_id == site_id,
                Camera.camera_id == camera_id
            )
        )
    )
    camera = result.scalar_one_or_none()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    # Stop streaming
    streaming_service.stop_stream(camera_id)
    
    return {
        "message": "Camera stream stopped successfully",
        "camera_id": camera_id,
        "stream_active": False
    }


@router.get("/sites/{site_id}/cameras/{camera_id}/stream/status")
async def get_camera_stream_status(
    site_id: str,
    camera_id: str,
    user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    """Get streaming status for a specific camera"""
    tenant_id = user["tenant_id"]
    await db.set_tenant_context(db_session, tenant_id)
    
    # Verify camera exists
    result = await db_session.execute(
        select(Camera).where(
            and_(
                Camera.tenant_id == tenant_id,
                Camera.site_id == site_id,
                Camera.camera_id == camera_id
            )
        )
    )
    camera = result.scalar_one_or_none()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    # Get stream info
    stream_info = streaming_service.get_stream_info(camera_id)
    is_active = streaming_service.is_stream_active(camera_id)
    
    return {
        "camera_id": camera_id,
        "stream_active": is_active,
        "stream_info": stream_info
    }


@router.get("/sites/{site_id}/cameras/{camera_id}/stream/feed")
async def get_camera_stream_feed(
    site_id: str,
    camera_id: str,
    user: Dict = Depends(get_current_user_for_stream),
    db_session: AsyncSession = Depends(get_db_session)
):
    """Get live video feed for a camera (MJPEG stream)"""
    tenant_id = user["tenant_id"]
    await db.set_tenant_context(db_session, tenant_id)
    
    # Verify camera exists
    result = await db_session.execute(
        select(Camera).where(
            and_(
                Camera.tenant_id == tenant_id,
                Camera.site_id == site_id,
                Camera.camera_id == camera_id
            )
        )
    )
    camera = result.scalar_one_or_none()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    # Check if stream is active
    if not streaming_service.is_stream_active(camera_id):
        raise HTTPException(status_code=404, detail="Camera stream is not active")
    
    return StreamingResponse(
        streaming_service.stream_frames(camera_id),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@router.get("/streaming/debug")
async def get_streaming_debug_info(
    user: Dict = Depends(get_current_user)
):
    """Get debug information about camera streaming service"""
    device_status = streaming_service.get_device_status()
    return {
        "streaming_service_status": device_status,
        "message": "This endpoint helps debug camera streaming conflicts and device usage"
    }


@router.get("/diagnostics/cameras")
async def run_camera_diagnostics(
    user: Dict = Depends(get_current_user)
):
    """Run comprehensive camera diagnostic tests"""
    report = camera_diagnostics.generate_full_report()
    return {
        "diagnostic_report": report,
        "message": "This endpoint tests camera enumeration and simultaneous access capabilities"
    }