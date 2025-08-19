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
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from .core.config import settings
from .core.database import get_db_session, db
from .core.middleware import tenant_context_middleware
from .core.security import mint_jwt, get_current_user
from .core.milvus_client import milvus_client
from .core.minio_client import minio_client
from .models.database import Tenant, Site, Camera, Staff, Customer, Visit, ApiKey
from .services.face_service import face_service, staff_service
from pkg_common.models import FaceDetectedEvent


# Application lifespan management
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        await milvus_client.connect()
        await minio_client.setup_buckets()
        logging.info("Successfully connected to external services")
    except Exception as e:
        logging.error(f"Failed to initialize services: {e}")
    
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
    camera_id: str
    name: str
    rtsp_url: Optional[str] = None


class CameraResponse(BaseModel):
    tenant_id: str
    site_id: str
    camera_id: str
    name: str
    rtsp_url: Optional[str]
    is_active: bool
    created_at: datetime


class StaffCreate(BaseModel):
    staff_id: str
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


class CustomerResponse(BaseModel):
    tenant_id: str
    customer_id: str
    name: Optional[str]
    gender: Optional[str]
    first_seen: datetime
    last_seen: Optional[datetime]
    visit_count: int


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
    person_id: Optional[str]
    similarity: float
    visit_id: Optional[str]
    person_type: str


# ===============================
# Health & Auth Endpoints
# ===============================

@app.get("/v1/health")
async def health():
    return {"status": "ok", "env": settings.env, "timestamp": datetime.now(timezone.utc)}


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
        camera_id=camera.camera_id,
        name=camera.name,
        rtsp_url=camera.rtsp_url
    )
    db_session.add(new_camera)
    await db_session.commit()
    return new_camera


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
    
    # Enroll staff with face embedding if provided
    if staff.face_embedding:
        await staff_service.enroll_staff_member(
            db_session=db_session,
            tenant_id=user["tenant_id"],
            staff_id=staff.staff_id,
            name=staff.name,
            face_embedding=staff.face_embedding,
            site_id=staff.site_id
        )
    else:
        new_staff = Staff(
            tenant_id=user["tenant_id"],
            staff_id=staff.staff_id,
            name=staff.name,
            site_id=staff.site_id
        )
        db_session.add(new_staff)
        await db_session.commit()
    
    # Return the created staff member
    result = await db_session.execute(
        select(Staff).where(
            and_(Staff.tenant_id == user["tenant_id"], Staff.staff_id == staff.staff_id)
        )
    )
    return result.scalar_one()


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
        query = query.where(Visit.timestamp >= start_time)
    if end_time:
        query = query.where(Visit.timestamp <= end_time)
    
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
            func.sum(func.case((Visit.person_type == "staff", 1), else_=0)).label("staff_visits"),
            func.sum(func.case((Visit.person_type == "customer", 1), else_=0)).label("customer_visits"),
        )
        .where(Visit.tenant_id == user["tenant_id"])
        .group_by(time_trunc)
        .order_by(time_trunc.desc())
    )
    
    if site_id:
        query = query.where(Visit.site_id == site_id)
    if start_date:
        query = query.where(Visit.timestamp >= start_date)
    if end_date:
        query = query.where(Visit.timestamp <= end_date)
    
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
    uvicorn.run(app, host=settings.host, port=settings.port),
    }
