from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from .models.database import CameraType


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