from __future__ import annotations

import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Header
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select, func, and_, case, update
from sqlalchemy.ext.asyncio import AsyncSession

from .core.config import settings
from .core.database import get_db_session, db
from .core.middleware import tenant_context_middleware
from .core.security import mint_jwt, get_current_user, verify_jwt, get_current_user_for_stream
from .core.milvus_client import milvus_client
from .core.minio_client import minio_client
from .models.database import Tenant, Site, Camera, Staff, Customer, Visit, ApiKey, CameraType, StaffFaceImage
from .services.face_service import face_service, staff_service
from .services.face_processing_service import face_processing_service
from pkg_common.models import FaceDetectedEvent


async def auto_start_camera_streams():
    """Auto-start all active camera streams on API startup"""
    try:
        from .core.database import get_db_session
        
        async for db_session in get_db_session():
            try:
                # Get all active cameras across all tenants
                result = await db_session.execute(
                    select(Camera).where(Camera.is_active == True)
                )
                cameras = result.scalars().all()
                
                started_count = 0
                for camera in cameras:
                    success = streaming_service.start_stream(
                        camera_id=camera.camera_id,
                        camera_type=camera.camera_type.value,
                        rtsp_url=camera.rtsp_url,
                        device_index=camera.device_index
                    )
                    if success:
                        started_count += 1
                        logging.info(f"Auto-started stream for camera {camera.camera_id}")
                    else:
                        logging.warning(f"Failed to auto-start stream for camera {camera.camera_id}")
                
                logging.info(f"Auto-started {started_count} camera streams")
                break  # Only use the first database session
                
            except Exception as e:
                logging.error(f"Error auto-starting camera streams: {e}")
                break
                
    except Exception as e:
        logging.error(f"Failed to get database session for auto-start: {e}")


# Application lifespan management
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        await milvus_client.connect()
        logging.info("Connected to Milvus")
    except Exception as e:
        logging.warning(f"Failed to connect to Milvus: {e}")
    
    try:
        await minio_client.setup_buckets()
        logging.info("Connected to MinIO")
    except Exception as e:
        logging.warning(f"Failed to connect to MinIO: {e}")
    
    # Auto-start all active camera streams
    try:
        await auto_start_camera_streams()
        logging.info("Auto-started camera streams")
    except Exception as e:
        logging.warning(f"Failed to auto-start camera streams: {e}")
    
    logging.info("API startup completed")
    
    yield
    
    # Shutdown
    try:
        # Cleanup camera streams
        streaming_service.cleanup_all_streams()
        logging.info("Cleaned up camera streams")
    except Exception as e:
        logging.error(f"Failed to cleanup camera streams: {e}")
    
    try:
        await milvus_client.disconnect()
        await db.close()
        logging.info("Successfully disconnected from services")
    except Exception as e:
        logging.error(f"Error during shutdown: {e}")

from .services.camera_streaming_service import streaming_service


tags_metadata = [
    {
        "name": "Health & Monitoring",
        "description": "System health checks and monitoring endpoints",
    },
    {
        "name": "Authentication",
        "description": "User authentication and token management",
    },
    {
        "name": "Tenant Management",
        "description": "Multi-tenant administration (System Admin only)",
    },
    {
        "name": "Site Management", 
        "description": "Site locations and configuration management",
    },
    {
        "name": "Camera Management",
        "description": "Camera devices and video streaming operations",
    },
    {
        "name": "Staff Management",
        "description": "Staff member profiles and face recognition training",
    },
    {
        "name": "Customer Management",
        "description": "Customer profiles and visit history",
    },
    {
        "name": "Events & Detection",
        "description": "Real-time face detection and recognition events",
    },
    {
        "name": "Visits & Analytics",
        "description": "Visit tracking, reporting, and analytics",
    },
    {
        "name": "File Management",
        "description": "File serving and download endpoints",
    },
]

app = FastAPI(
    title="Customer Visits API",
    version="0.1.0",
    openapi_url="/v1/openapi.json",
    lifespan=lifespan,
    openapi_tags=tags_metadata
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.middleware("http")(tenant_context_middleware)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def to_naive_utc(dt: datetime) -> datetime:
    """Convert timezone-aware datetime to UTC and make timezone-naive for PostgreSQL compatibility."""
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


# ===============================
# Auth & Token Models
# ===============================

class TokenRequest(BaseModel):
    grant_type: str = "password"
    username: Optional[str] = None
    password: Optional[str] = None
    api_key: Optional[str] = None
    tenant_id: str
    role: str = "worker"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ===============================
# Entity Models
# ===============================

class TenantCreate(BaseModel):
    tenant_id: str
    name: str


class TenantResponse(BaseModel):
    tenant_id: str
    name: str
    created_at: datetime


class SiteCreate(BaseModel):
    site_id: str
    name: str
    location: Optional[str] = None


class SiteResponse(BaseModel):
    tenant_id: str
    site_id: str
    name: str
    location: Optional[str]
    created_at: datetime


class CameraCreate(BaseModel):
    name: str
    camera_type: CameraType = CameraType.RTSP
    rtsp_url: Optional[str] = None
    device_index: Optional[int] = None


class CameraResponse(BaseModel):
    tenant_id: str
    site_id: str
    camera_id: str
    name: str
    camera_type: CameraType
    rtsp_url: Optional[str]
    device_index: Optional[int]
    is_active: bool
    created_at: datetime


class StaffCreate(BaseModel):
    name: str
    site_id: Optional[str] = None
    face_embedding: Optional[List[float]] = None


class StaffResponse(BaseModel):
    tenant_id: str
    staff_id: str
    name: str
    site_id: Optional[str]
    is_active: bool
    created_at: datetime

class StaffFaceImageCreate(BaseModel):
    image_data: str  # Base64 encoded image
    is_primary: bool = False

class StaffFaceImageResponse(BaseModel):
    tenant_id: str
    image_id: str  
    staff_id: str
    image_path: str
    face_landmarks: Optional[List[List[float]]] = None  # 5-point landmarks
    is_primary: bool
    created_at: datetime

class StaffWithFacesResponse(StaffResponse):
    face_images: List[StaffFaceImageResponse] = []

class FaceRecognitionTestRequest(BaseModel):
    test_image: str  # Base64 encoded test image

class FaceRecognitionTestResponse(BaseModel):
    matches: List[dict]  # List of potential matches with similarity scores
    best_match: Optional[dict] = None
    processing_info: dict


class CustomerResponse(BaseModel):
    tenant_id: str
    customer_id: str
    name: Optional[str]
    gender: Optional[str]
    estimated_age_range: Optional[str]
    phone: Optional[str]
    email: Optional[str]
    first_seen: datetime
    last_seen: Optional[datetime]
    visit_count: int

class CustomerCreate(BaseModel):
    name: Optional[str] = None
    gender: Optional[str] = None
    estimated_age_range: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    gender: Optional[str] = None
    estimated_age_range: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


class VisitResponse(BaseModel):
    tenant_id: str
    visit_id: str
    person_id: str
    person_type: str
    site_id: str
    camera_id: str
    timestamp: datetime
    confidence_score: float
    image_path: Optional[str]


class FaceEventResponse(BaseModel):
    match: str
    person_id: Optional[int]
    similarity: float
    visit_id: Optional[str]
    person_type: str


# ===============================
# Health & Auth Endpoints
# ===============================

@app.get("/v1/health", tags=["Health & Monitoring"])
async def health():
    return {"status": "ok", "env": settings.env, "timestamp": datetime.now(timezone.utc)}

@app.get("/v1/health/milvus", tags=["Health & Monitoring"])
async def health_milvus():
    """Get Milvus connection health status"""
    milvus_health = await milvus_client.health_check()
    return milvus_health

@app.get("/v1/health/face-processing", tags=["Health & Monitoring"])
async def health_face_processing():
    """Check if face processing dependencies are available."""
    try:
        from .services.face_processing_service import FACE_PROCESSING_AVAILABLE
        return {
            "face_processing_available": FACE_PROCESSING_AVAILABLE,
            "status": "ready" if FACE_PROCESSING_AVAILABLE else "dependencies_missing",
            "message": "Face processing is ready" if FACE_PROCESSING_AVAILABLE else "Install Pillow, OpenCV, and NumPy to enable face processing"
        }
    except Exception as e:
        return {
            "face_processing_available": False,
            "status": "error",
            "message": f"Error checking face processing status: {e}"
        }


@app.post("/v1/auth/token", response_model=TokenResponse, tags=["Authentication"])
async def issue_token(payload: TokenRequest):
    if payload.grant_type == "api_key":
        if payload.api_key != os.getenv("WORKER_API_KEY", "dev-api-key"):
            raise HTTPException(status_code=401, detail="Invalid API key")
    else:
        if not (payload.username and payload.password):
            raise HTTPException(status_code=400, detail="Missing credentials")
        # Dev auth: accept any non-empty values
    
    token = mint_jwt(
        sub=payload.username or "worker",
        role=payload.role,
        tenant_id=payload.tenant_id
    )
    return TokenResponse(access_token=token)


@app.get("/v1/me", tags=["Authentication"])
async def get_current_user_info(user: dict = Depends(get_current_user)):
    return user


# ===============================
# Tenant Management (System Admin Only)
# ===============================

@app.get("/v1/tenants", response_model=List[TenantResponse], tags=["Tenant Management"])
async def list_tenants(
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    if user["role"] != "system_admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    
    await db.set_tenant_context(db_session, user["tenant_id"])
    
    result = await db_session.execute(select(Tenant))
    tenants = result.scalars().all()
    return tenants


@app.post("/v1/tenants", response_model=TenantResponse, tags=["Tenant Management"])
async def create_tenant(
    tenant: TenantCreate,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    if user["role"] != "system_admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    
    new_tenant = Tenant(tenant_id=tenant.tenant_id, name=tenant.name)
    db_session.add(new_tenant)
    await db_session.commit()
    return new_tenant


# ===============================
# Sites Management
# ===============================

@app.get("/v1/sites", response_model=List[SiteResponse], tags=["Site Management"])
async def list_sites(
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    await db.set_tenant_context(db_session, user["tenant_id"])
    
    result = await db_session.execute(
        select(Site).where(Site.tenant_id == user["tenant_id"])
    )
    sites = result.scalars().all()
    return sites


@app.post("/v1/sites", response_model=SiteResponse, tags=["Site Management"])
async def create_site(
    site: SiteCreate,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    await db.set_tenant_context(db_session, user["tenant_id"])
    
    new_site = Site(
        tenant_id=user["tenant_id"],
        site_id=site.site_id,
        name=site.name,
        location=site.location
    )
    db_session.add(new_site)
    await db_session.commit()
    return new_site


# ===============================
# Cameras Management
# ===============================

@app.get("/v1/sites/{site_id}/cameras", response_model=List[CameraResponse], tags=["Camera Management"])
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


@app.post("/v1/sites/{site_id}/cameras", response_model=CameraResponse, tags=["Camera Management"])
async def create_camera(
    site_id: str,
    camera: CameraCreate,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    await db.set_tenant_context(db_session, user["tenant_id"])
    
    new_camera = Camera(
        tenant_id=user["tenant_id"],
        site_id=site_id,
        name=camera.name,
        camera_type=camera.camera_type,
        rtsp_url=camera.rtsp_url,
        device_index=camera.device_index
    )
    db_session.add(new_camera)
    await db_session.commit()
    return new_camera

@app.get("/v1/sites/{site_id}/cameras/{camera_id}", response_model=CameraResponse, tags=["Camera Management"])
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


@app.put("/v1/sites/{site_id}/cameras/{camera_id}", response_model=CameraResponse, tags=["Camera Management"])
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


@app.delete("/v1/sites/{site_id}/cameras/{camera_id}", tags=["Camera Management"])
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

@app.post("/v1/sites/{site_id}/cameras/{camera_id}/stream/start", tags=["Camera Management"])
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


@app.post("/v1/sites/{site_id}/cameras/{camera_id}/stream/stop", tags=["Camera Management"])
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


@app.get("/v1/sites/{site_id}/cameras/{camera_id}/stream/status", tags=["Camera Management"])
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


@app.get("/v1/sites/{site_id}/cameras/{camera_id}/stream/feed", tags=["Camera Management"])
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
    
    from fastapi.responses import StreamingResponse
    
    return StreamingResponse(
        streaming_service.stream_frames(camera_id),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


# ===============================
# Staff Management
# ===============================

@app.get("/v1/staff", response_model=List[StaffResponse], tags=["Staff Management"])
async def list_staff(
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    await db.set_tenant_context(db_session, user["tenant_id"])
    
    result = await db_session.execute(
        select(Staff).where(Staff.tenant_id == user["tenant_id"])
    )
    staff_members = result.scalars().all()
    return staff_members


@app.post("/v1/staff", response_model=StaffResponse, tags=["Staff Management"])
async def create_staff(
    staff: StaffCreate,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    await db.set_tenant_context(db_session, user["tenant_id"])
    
    # Generate staff ID
    import uuid
    staff_id = f"staff-{uuid.uuid4().hex[:8]}"
    
    # Create staff member
    new_staff = Staff(
        tenant_id=user["tenant_id"],
        staff_id=staff_id,
        name=staff.name,
        site_id=staff.site_id
    )
    db_session.add(new_staff)
    await db_session.commit()
    await db_session.refresh(new_staff)
    
    # Enroll with face embedding if provided
    if staff.face_embedding:
        await staff_service.enroll_staff_member(
            db_session=db_session,
            tenant_id=user["tenant_id"],
            staff_id=new_staff.staff_id,
            name=staff.name,
            face_embedding=staff.face_embedding,
            site_id=staff.site_id
        )
    
    # Return the created staff member
    return new_staff

@app.get("/v1/staff/{staff_id}", response_model=StaffResponse, tags=["Staff Management"])
async def get_staff_member(
    staff_id: str,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    await db.set_tenant_context(db_session, user["tenant_id"])
    
    result = await db_session.execute(
        select(Staff).where(
            and_(Staff.tenant_id == user["tenant_id"], Staff.staff_id == staff_id)
        )
    )
    staff_member = result.scalar_one_or_none()
    if not staff_member:
        raise HTTPException(status_code=404, detail="Staff member not found")
    
    return staff_member


@app.put("/v1/staff/{staff_id}", response_model=StaffResponse, tags=["Staff Management"])
async def update_staff(
    staff_id: str,
    staff_update: StaffCreate,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    await db.set_tenant_context(db_session, user["tenant_id"])
    
    result = await db_session.execute(
        select(Staff).where(
            and_(Staff.tenant_id == user["tenant_id"], Staff.staff_id == staff_id)
        )
    )
    staff_member = result.scalar_one_or_none()
    if not staff_member:
        raise HTTPException(status_code=404, detail="Staff member not found")
    
    # Update staff fields
    staff_member.name = staff_update.name
    staff_member.site_id = staff_update.site_id
    
    # Handle face embedding update
    if staff_update.face_embedding:
        # Delete existing embeddings and create new ones
        await staff_service.enroll_staff_member(
            db_session=db_session,
            tenant_id=user["tenant_id"],
            staff_id=staff_id,
            name=staff_update.name,
            face_embedding=staff_update.face_embedding,
            site_id=staff_update.site_id,
            update_existing=True
        )
    
    await db_session.commit()
    await db_session.refresh(staff_member)
    return staff_member


@app.delete("/v1/staff/{staff_id}", tags=["Staff Management"])
async def delete_staff(
    staff_id: str,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    await db.set_tenant_context(db_session, user["tenant_id"])
    
    result = await db_session.execute(
        select(Staff).where(
            and_(Staff.tenant_id == user["tenant_id"], Staff.staff_id == staff_id)
        )
    )
    staff_member = result.scalar_one_or_none()
    if not staff_member:
        raise HTTPException(status_code=404, detail="Staff member not found")
    
    # Delete from Milvus as well
    try:
        await milvus_client.delete_person_embeddings(user["tenant_id"], staff_id)
    except Exception as e:
        logger.warning(f"Failed to delete staff embeddings from Milvus: {e}")
    
    await db_session.delete(staff_member)
    await db_session.commit()
    return {"message": "Staff member deleted successfully"}

# ===============================
# Staff Face Images API
# ===============================

@app.get("/v1/staff/{staff_id}/faces", response_model=List[StaffFaceImageResponse], tags=["Staff Management"])
async def get_staff_face_images(
    staff_id: str,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    """Get all face images for a staff member."""
    await db.set_tenant_context(db_session, user["tenant_id"])
    
    # Verify staff exists
    staff_result = await db_session.execute(
        select(Staff).where(
            and_(Staff.tenant_id == user["tenant_id"], Staff.staff_id == staff_id)
        )
    )
    if not staff_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Staff member not found")
    
    # Get face images
    result = await db_session.execute(
        select(StaffFaceImage).where(
            and_(
                StaffFaceImage.tenant_id == user["tenant_id"],
                StaffFaceImage.staff_id == staff_id
            )
        ).order_by(StaffFaceImage.created_at.desc())
    )
    
    face_images = result.scalars().all()
    
    # Parse landmarks from JSON
    response_images = []
    for img in face_images:
        response_data = {
            "tenant_id": img.tenant_id,
            "image_id": img.image_id,
            "staff_id": img.staff_id,
            "image_path": img.image_path,
            "is_primary": img.is_primary,
            "created_at": img.created_at,
            "face_landmarks": json.loads(img.face_landmarks) if img.face_landmarks else None
        }
        response_images.append(StaffFaceImageResponse(**response_data))
    
    return response_images

@app.get("/v1/staff/{staff_id}/details", response_model=StaffWithFacesResponse, tags=["Staff Management"])
async def get_staff_with_faces(
    staff_id: str,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    """Get staff details with all face images."""
    await db.set_tenant_context(db_session, user["tenant_id"])
    
    # Get staff member
    staff_result = await db_session.execute(
        select(Staff).where(
            and_(Staff.tenant_id == user["tenant_id"], Staff.staff_id == staff_id)
        )
    )
    staff = staff_result.scalar_one_or_none()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")
    
    # Get face images
    images_result = await db_session.execute(
        select(StaffFaceImage).where(
            and_(
                StaffFaceImage.tenant_id == user["tenant_id"],
                StaffFaceImage.staff_id == staff_id
            )
        ).order_by(StaffFaceImage.created_at.desc())
    )
    
    face_images = images_result.scalars().all()
    
    # Build response
    response_images = []
    for img in face_images:
        response_data = {
            "tenant_id": img.tenant_id,
            "image_id": img.image_id,
            "staff_id": img.staff_id,
            "image_path": img.image_path,
            "is_primary": img.is_primary,
            "created_at": img.created_at,
            "face_landmarks": json.loads(img.face_landmarks) if img.face_landmarks else None
        }
        response_images.append(StaffFaceImageResponse(**response_data))
    
    staff_data = {
        "tenant_id": staff.tenant_id,
        "staff_id": staff.staff_id,
        "name": staff.name,
        "site_id": staff.site_id,
        "is_active": staff.is_active,
        "created_at": staff.created_at,
        "face_images": response_images
    }
    
    return StaffWithFacesResponse(**staff_data)

@app.post("/v1/staff/{staff_id}/faces", response_model=StaffFaceImageResponse, tags=["Staff Management"])
async def upload_staff_face_image(
    staff_id: str,
    face_data: StaffFaceImageCreate,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    """Upload a new face image for a staff member."""
    await db.set_tenant_context(db_session, user["tenant_id"])
    
    # Verify staff exists
    staff_result = await db_session.execute(
        select(Staff).where(
            and_(Staff.tenant_id == user["tenant_id"], Staff.staff_id == staff_id)
        )
    )
    if not staff_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Staff member not found")
    
    try:
        # Process face image
        processing_result = await face_processing_service.process_staff_face_image(
            base64_image=face_data.image_data,
            tenant_id=user["tenant_id"],
            staff_id=staff_id
        )
        
        if not processing_result['success']:
            raise HTTPException(
                status_code=400, 
                detail=f"Face processing failed: {processing_result.get('error', 'Unknown error')}"
            )
        
        # If this is set as primary, update existing primary images
        if face_data.is_primary:
            await db_session.execute(
                update(StaffFaceImage)
                .where(
                    and_(
                        StaffFaceImage.tenant_id == user["tenant_id"],
                        StaffFaceImage.staff_id == staff_id,
                        StaffFaceImage.is_primary == True
                    )
                )
                .values(is_primary=False)
            )
        
        # Create face image record
        face_image = StaffFaceImage(
            tenant_id=user["tenant_id"],
            image_id=processing_result['image_id'],
            staff_id=staff_id,
            image_path=processing_result['image_path'],
            face_landmarks=json.dumps(processing_result['landmarks']),
            face_embedding=json.dumps(processing_result['embedding']),
            is_primary=face_data.is_primary
        )
        
        db_session.add(face_image)
        
        # Store embedding in Milvus
        await milvus_client.insert_embedding(
            tenant_id=user["tenant_id"],
            person_id=staff_id,
            person_type="staff",
            embedding=processing_result['embedding'],
            created_at=int(datetime.utcnow().timestamp())
        )
        
        await db_session.commit()
        await db_session.refresh(face_image)
        
        # Build response
        response_data = {
            "tenant_id": face_image.tenant_id,
            "image_id": face_image.image_id,
            "staff_id": face_image.staff_id,
            "image_path": face_image.image_path,
            "is_primary": face_image.is_primary,
            "created_at": face_image.created_at,
            "face_landmarks": json.loads(face_image.face_landmarks) if face_image.face_landmarks else None
        }
        
        return StaffFaceImageResponse(**response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload staff face image: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.delete("/v1/staff/{staff_id}/faces/{image_id}", tags=["Staff Management"])
async def delete_staff_face_image(
    staff_id: str,
    image_id: str,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    """Delete a staff face image."""
    await db.set_tenant_context(db_session, user["tenant_id"])
    
    # Get the face image
    result = await db_session.execute(
        select(StaffFaceImage).where(
            and_(
                StaffFaceImage.tenant_id == user["tenant_id"],
                StaffFaceImage.staff_id == staff_id,
                StaffFaceImage.image_id == image_id
            )
        )
    )
    
    face_image = result.scalar_one_or_none()
    if not face_image:
        raise HTTPException(status_code=404, detail="Face image not found")
    
    try:
        # Delete from MinIO
        await minio_client.delete_file("faces-derived", face_image.image_path)
        
        # Delete embedding from Milvus 
        # Note: Since we don't have metadata support, we delete by person_id
        # This will delete all embeddings for this staff member
        await milvus_client.delete_person_embeddings(user["tenant_id"], staff_id)
        
        # Delete from database
        await db_session.delete(face_image)
        await db_session.commit()
        
        return {"message": "Face image deleted successfully"}
        
    except Exception as e:
        logger.error(f"Failed to delete face image: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete face image")

@app.put("/v1/staff/{staff_id}/faces/{image_id}/recalculate", tags=["Staff Management"])
async def recalculate_face_embedding(
    staff_id: str,
    image_id: str,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    """Recalculate face landmarks and embedding for an existing image."""
    await db.set_tenant_context(db_session, user["tenant_id"])
    
    # Get the face image
    result = await db_session.execute(
        select(StaffFaceImage).where(
            and_(
                StaffFaceImage.tenant_id == user["tenant_id"],
                StaffFaceImage.staff_id == staff_id,
                StaffFaceImage.image_id == image_id
            )
        )
    )
    
    face_image = result.scalar_one_or_none()
    if not face_image:
        raise HTTPException(status_code=404, detail="Face image not found")
    
    try:
        # Download image from MinIO
        image_data = await minio_client.download_file("faces-derived", face_image.image_path)
        
        # Convert to base64 for processing
        import base64
        image_b64 = base64.b64encode(image_data).decode('utf-8')
        
        # Reprocess the image
        processing_result = await face_processing_service.process_staff_face_image(
            base64_image=image_b64,
            tenant_id=user["tenant_id"],
            staff_id=staff_id
        )
        
        if not processing_result['success']:
            raise HTTPException(
                status_code=400, 
                detail=f"Face reprocessing failed: {processing_result.get('error', 'Unknown error')}"
            )
        
        # Update the face image record
        face_image.face_landmarks = json.dumps(processing_result['landmarks'])
        face_image.face_embedding = json.dumps(processing_result['embedding'])
        face_image.updated_at = datetime.utcnow()
        
        # Update embedding in Milvus
        # Note: Since we don't have metadata support, we delete by person_id and recreate
        await milvus_client.delete_person_embeddings(user["tenant_id"], staff_id)
        
        await milvus_client.insert_embedding(
            tenant_id=user["tenant_id"],
            person_id=staff_id,
            person_type="staff",
            embedding=processing_result['embedding'],
            created_at=int(datetime.utcnow().timestamp())
        )
        
        await db_session.commit()
        await db_session.refresh(face_image)
        
        return {
            "message": "Face landmarks and embedding recalculated successfully",
            "processing_info": {
                "face_count": processing_result['face_count'],
                "confidence": processing_result['confidence']
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to recalculate face embedding: {e}")
        raise HTTPException(status_code=500, detail="Failed to recalculate face embedding")

@app.post("/v1/staff/{staff_id}/test-recognition", response_model=FaceRecognitionTestResponse, tags=["Staff Management"])
async def test_face_recognition(
    staff_id: str,
    test_data: FaceRecognitionTestRequest,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    """Test face recognition accuracy by uploading a test image."""
    await db.set_tenant_context(db_session, user["tenant_id"])
    
    # Verify staff exists
    staff_result = await db_session.execute(
        select(Staff).where(
            and_(Staff.tenant_id == user["tenant_id"], Staff.staff_id == staff_id)
        )
    )
    staff = staff_result.scalar_one_or_none()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")
    
    try:
        # Get all staff embeddings for comparison
        all_staff_result = await db_session.execute(
            select(StaffFaceImage).where(
                StaffFaceImage.tenant_id == user["tenant_id"]
            )
        )
        
        staff_embeddings = []
        for img in all_staff_result.scalars().all():
            if img.face_embedding:
                # Get staff name
                staff_name_result = await db_session.execute(
                    select(Staff.name).where(
                        and_(
                            Staff.tenant_id == user["tenant_id"],
                            Staff.staff_id == img.staff_id
                        )
                    )
                )
                staff_name = staff_name_result.scalar_one_or_none() or "Unknown"
                
                staff_embeddings.append({
                    'staff_id': img.staff_id,
                    'image_id': img.image_id,
                    'name': staff_name,
                    'embedding': json.loads(img.face_embedding)
                })
        
        # Test recognition
        recognition_result = await face_processing_service.test_face_recognition(
            test_image_b64=test_data.test_image,
            tenant_id=user["tenant_id"],
            staff_embeddings=staff_embeddings
        )
        
        if not recognition_result['success']:
            raise HTTPException(
                status_code=400,
                detail=f"Recognition test failed: {recognition_result.get('error', 'Unknown error')}"
            )
        
        return FaceRecognitionTestResponse(
            matches=recognition_result['matches'],
            best_match=recognition_result['best_match'],
            processing_info=recognition_result['processing_info']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Face recognition test failed: {e}")
        raise HTTPException(status_code=500, detail="Recognition test failed")


# ===============================
# Customers
# ===============================

@app.get("/v1/customers", response_model=List[CustomerResponse], tags=["Customer Management"])
async def list_customers(
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    await db.set_tenant_context(db_session, user["tenant_id"])
    
    result = await db_session.execute(
        select(Customer)
        .where(Customer.tenant_id == user["tenant_id"])
        .order_by(Customer.last_seen.desc())
        .limit(limit)
        .offset(offset)
    )
    customers = result.scalars().all()
    return customers

@app.post("/v1/customers", response_model=CustomerResponse, tags=["Customer Management"])
async def create_customer(
    customer: CustomerCreate,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    await db.set_tenant_context(db_session, user["tenant_id"])
    
    # Generate customer ID
    import uuid
    customer_id = f"cust-{uuid.uuid4().hex[:8]}"
    
    new_customer = Customer(
        tenant_id=user["tenant_id"],
        customer_id=customer_id,
        name=customer.name,
        gender=customer.gender,
        estimated_age_range=customer.estimated_age_range,
        phone=customer.phone,
        email=customer.email
    )
    db_session.add(new_customer)
    await db_session.commit()
    await db_session.refresh(new_customer)
    return new_customer


@app.get("/v1/customers/{customer_id}", response_model=CustomerResponse, tags=["Customer Management"])
async def get_customer(
    customer_id: str,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    await db.set_tenant_context(db_session, user["tenant_id"])
    
    result = await db_session.execute(
        select(Customer).where(
            and_(Customer.tenant_id == user["tenant_id"], Customer.customer_id == customer_id)
        )
    )
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    return customer


@app.put("/v1/customers/{customer_id}", response_model=CustomerResponse, tags=["Customer Management"])
async def update_customer(
    customer_id: str,
    customer_update: CustomerUpdate,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    await db.set_tenant_context(db_session, user["tenant_id"])
    
    result = await db_session.execute(
        select(Customer).where(
            and_(Customer.tenant_id == user["tenant_id"], Customer.customer_id == customer_id)
        )
    )
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    # Update customer fields
    if customer_update.name is not None:
        customer.name = customer_update.name
    if customer_update.gender is not None:
        customer.gender = customer_update.gender
    if customer_update.estimated_age_range is not None:
        customer.estimated_age_range = customer_update.estimated_age_range
    if customer_update.phone is not None:
        customer.phone = customer_update.phone
    if customer_update.email is not None:
        customer.email = customer_update.email
    
    await db_session.commit()
    await db_session.refresh(customer)
    return customer


@app.delete("/v1/customers/{customer_id}", tags=["Customer Management"])
async def delete_customer(
    customer_id: str,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    await db.set_tenant_context(db_session, user["tenant_id"])
    
    result = await db_session.execute(
        select(Customer).where(
            and_(Customer.tenant_id == user["tenant_id"], Customer.customer_id == customer_id)
        )
    )
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    # Delete customer embeddings from Milvus
    try:
        await milvus_client.delete_person_embeddings(user["tenant_id"], customer_id)
    except Exception as e:
        logger.warning(f"Failed to delete customer embeddings from Milvus: {e}")
    
    await db_session.delete(customer)
    await db_session.commit()
    return {"message": "Customer deleted successfully"}


# ===============================
# Events Processing
# ===============================

@app.post("/v1/events/face", response_model=FaceEventResponse, tags=["Events & Detection"])
async def process_face_event(
    event: FaceDetectedEvent,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    await db.set_tenant_context(db_session, user["tenant_id"])
    
    result = await face_service.process_face_event(
        event=event,
        db_session=db_session,
        tenant_id=user["tenant_id"]
    )
    
    return FaceEventResponse(**result)


# ===============================
# Visits
# ===============================

@app.get("/v1/visits", response_model=List[VisitResponse], tags=["Visits & Analytics"])
async def list_visits(
    site_id: Optional[str] = Query(None),
    person_id: Optional[str] = Query(None),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    await db.set_tenant_context(db_session, user["tenant_id"])
    
    query = select(Visit).where(Visit.tenant_id == user["tenant_id"])
    
    if site_id:
        query = query.where(Visit.site_id == site_id)
    if person_id:
        query = query.where(Visit.person_id == person_id)
    if start_time:
        query = query.where(Visit.timestamp >= to_naive_utc(start_time))
    if end_time:
        query = query.where(Visit.timestamp <= to_naive_utc(end_time))
    
    query = query.order_by(Visit.timestamp.desc()).limit(limit).offset(offset)
    
    result = await db_session.execute(query)
    visits = result.scalars().all()
    return visits


# ===============================
# Reports
# ===============================

@app.get("/v1/reports/visitors", tags=["Visits & Analytics"])
async def get_visitor_report(
    site_id: Optional[str] = Query(None),
    granularity: str = Query("day", regex="^(hour|day|week|month)$"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    await db.set_tenant_context(db_session, user["tenant_id"])
    
    # Build time granularity function
    time_trunc = {
        "hour": func.date_trunc("hour", Visit.timestamp),
        "day": func.date_trunc("day", Visit.timestamp),
        "week": func.date_trunc("week", Visit.timestamp),
        "month": func.date_trunc("month", Visit.timestamp),
    }[granularity]
    
    query = (
        select(
            time_trunc.label("period"),
            func.count().label("total_visits"),
            func.count(func.distinct(Visit.person_id)).label("unique_visitors"),
            func.sum(case((Visit.person_type == "staff", 1), else_=0)).label("staff_visits"),
            func.sum(case((Visit.person_type == "customer", 1), else_=0)).label("customer_visits"),
        )
        .where(Visit.tenant_id == user["tenant_id"])
        .group_by(time_trunc)
        .order_by(time_trunc.desc())
    )
    
    if site_id:
        query = query.where(Visit.site_id == site_id)
    if start_date:
        query = query.where(Visit.timestamp >= to_naive_utc(start_date))
    if end_date:
        query = query.where(Visit.timestamp <= to_naive_utc(end_date))
    
    result = await db_session.execute(query)
    
    return [
        {
            "period": row.period.isoformat() if row.period else None,
            "total_visits": int(row.total_visits),
            "unique_visitors": int(row.unique_visitors),
            "staff_visits": int(row.staff_visits or 0),
            "customer_visits": int(row.customer_visits or 0),
        }
        for row in result
    ]


# ===============================
# Files (Authenticated MinIO Proxy)
# ===============================

@app.get("/v1/files/{file_path:path}", tags=["File Management"])
async def serve_file(
    file_path: str,
    token: Optional[str] = Query(None),
    access_token: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
):
    """Serve files stored in MinIO with tenant-aware access control.

    Currently supports staff face images under paths like:
    staff-faces/{tenant_id}/<filename>.{jpg|png|webp|gif}
    """
    # Authenticate via Authorization header or ?token / ?access_token query param
    jwt_token: Optional[str] = None
    if authorization and authorization.startswith("Bearer "):
        jwt_token = authorization.split(" ", 1)[1]
    elif token:
        jwt_token = token
    elif access_token:
        jwt_token = access_token
    else:
        raise HTTPException(status_code=401, detail="Missing token")

    payload = verify_jwt(jwt_token)
    # Basic validation
    if not file_path or ".." in file_path or file_path.startswith("/"):
        raise HTTPException(status_code=400, detail="Invalid file path")

    # Restrict to staff face images and enforce tenant isolation
    if not file_path.startswith("staff-faces/"):
        raise HTTPException(status_code=404, detail="File not found")

    parts = file_path.split("/")
    if len(parts) < 3:
        raise HTTPException(status_code=404, detail="File not found")

    path_tenant_id = parts[1]
    if path_tenant_id != payload.get("tenant_id"):
        raise HTTPException(status_code=403, detail="Forbidden")

    # Determine content type by extension
    content_type = "application/octet-stream"
    lower = file_path.lower()
    if lower.endswith(".jpg") or lower.endswith(".jpeg"):
        content_type = "image/jpeg"
    elif lower.endswith(".png"):
        content_type = "image/png"
    elif lower.endswith(".webp"):
        content_type = "image/webp"
    elif lower.endswith(".gif"):
        content_type = "image/gif"

    try:
        data = await minio_client.download_file("faces-derived", file_path)
        return Response(content=data, media_type=content_type)
    except Exception:
        raise HTTPException(status_code=404, detail="File not found")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port)
