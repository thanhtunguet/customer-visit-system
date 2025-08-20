from __future__ import annotations

import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select, func, and_, case
from sqlalchemy.ext.asyncio import AsyncSession

from .core.config import settings
from .core.database import get_db_session, db
from .core.middleware import tenant_context_middleware
from .core.security import mint_jwt, get_current_user
from .core.milvus_client import milvus_client
from .core.minio_client import minio_client
from .models.database import Tenant, Site, Camera, Staff, Customer, Visit, ApiKey, CameraType
from .services.face_service import face_service, staff_service
from pkg_common.models import FaceDetectedEvent


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
    
    logging.info("API startup completed")
    
    yield
    
    # Shutdown
    try:
        await milvus_client.disconnect()
        await db.close()
        logging.info("Successfully disconnected from services")
    except Exception as e:
        logging.error(f"Error during shutdown: {e}")


app = FastAPI(
    title="Face Recognition API",
    version="0.1.0",
    openapi_url="/v1/openapi.json",
    lifespan=lifespan
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
    camera_id: int
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
    staff_id: int
    name: str
    site_id: Optional[str]
    is_active: bool
    created_at: datetime


class CustomerResponse(BaseModel):
    tenant_id: str
    customer_id: int
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
    person_id: int
    person_type: str
    site_id: str
    camera_id: int
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

@app.get("/v1/health")
async def health():
    return {"status": "ok", "env": settings.env, "timestamp": datetime.now(timezone.utc)}

@app.get("/v1/health/milvus")
async def health_milvus():
    """Get Milvus connection health status"""
    milvus_health = await milvus_client.health_check()
    return milvus_health


@app.post("/v1/auth/token", response_model=TokenResponse)
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


@app.get("/v1/me")
async def get_current_user_info(user: dict = Depends(get_current_user)):
    return user


# ===============================
# Tenant Management (System Admin Only)
# ===============================

@app.get("/v1/tenants", response_model=List[TenantResponse])
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


@app.post("/v1/tenants", response_model=TenantResponse)
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

@app.get("/v1/sites", response_model=List[SiteResponse])
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


@app.post("/v1/sites", response_model=SiteResponse)
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

@app.get("/v1/sites/{site_id}/cameras", response_model=List[CameraResponse])
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


@app.post("/v1/sites/{site_id}/cameras", response_model=CameraResponse)
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

@app.get("/v1/sites/{site_id}/cameras/{camera_id}", response_model=CameraResponse)
async def get_camera(
    site_id: str,
    camera_id: int,
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


@app.put("/v1/sites/{site_id}/cameras/{camera_id}", response_model=CameraResponse)
async def update_camera(
    site_id: str,
    camera_id: int,
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


@app.delete("/v1/sites/{site_id}/cameras/{camera_id}")
async def delete_camera(
    site_id: str,
    camera_id: int,
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


# ===============================
# Staff Management
# ===============================

@app.get("/v1/staff", response_model=List[StaffResponse])
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


@app.post("/v1/staff", response_model=StaffResponse)
async def create_staff(
    staff: StaffCreate,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    await db.set_tenant_context(db_session, user["tenant_id"])
    
    # Create staff member first to get auto-generated ID
    new_staff = Staff(
        tenant_id=user["tenant_id"],
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

@app.get("/v1/staff/{staff_id}", response_model=StaffResponse)
async def get_staff_member(
    staff_id: int,
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


@app.put("/v1/staff/{staff_id}", response_model=StaffResponse)
async def update_staff(
    staff_id: int,
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


@app.delete("/v1/staff/{staff_id}")
async def delete_staff(
    staff_id: int,
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
# Customers
# ===============================

@app.get("/v1/customers", response_model=List[CustomerResponse])
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

@app.post("/v1/customers", response_model=CustomerResponse)
async def create_customer(
    customer: CustomerCreate,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    await db.set_tenant_context(db_session, user["tenant_id"])
    
    new_customer = Customer(
        tenant_id=user["tenant_id"],
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


@app.get("/v1/customers/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: int,
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


@app.put("/v1/customers/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: int,
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


@app.delete("/v1/customers/{customer_id}")
async def delete_customer(
    customer_id: int,
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

@app.post("/v1/events/face", response_model=FaceEventResponse)
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

@app.get("/v1/visits", response_model=List[VisitResponse])
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

@app.get("/v1/reports/visitors")
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port)
