from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr

from .models.database import CameraType, UserRole

# ===============================
# Auth & Token Models
# ===============================


class TokenRequest(BaseModel):
    grant_type: str = "password"
    username: Optional[str] = None
    password: Optional[str] = None
    api_key: Optional[str] = None
    tenant_id: Optional[str] = None
    role: UserRole = UserRole.WORKER


class ViewSwitchRequest(BaseModel):
    target_tenant_id: Optional[str] = (
        None  # None for global view, string for tenant view
    )


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ===============================
# API Key Management Models
# ===============================


class ApiKeyCreate(BaseModel):
    name: str
    role: str = "worker"
    expires_at: Optional[datetime] = None


class ApiKeyResponse(BaseModel):
    key_id: str
    tenant_id: str
    name: str
    role: str
    is_active: bool
    last_used: Optional[datetime]
    expires_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class ApiKeyCreateResponse(BaseModel):
    """Response when creating API key - includes the plain text key"""

    key_id: str
    tenant_id: str
    name: str
    role: str
    api_key: str  # Plain text key - only shown once
    is_active: bool
    expires_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class ApiKeyUpdate(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None
    expires_at: Optional[datetime] = None


# ===============================
# User Management Models
# ===============================


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    first_name: str
    last_name: str
    password: str
    role: UserRole
    tenant_id: Optional[str] = None  # Required for non-system_admin roles
    site_id: Optional[int] = None  # Required for site_manager role
    is_active: bool = True


class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: Optional[UserRole] = None
    tenant_id: Optional[str] = None
    site_id: Optional[int] = None
    is_active: Optional[bool] = None


class UserPasswordUpdate(BaseModel):
    current_password: Optional[str] = None  # Required unless admin is changing
    new_password: str


class UserResponse(BaseModel):
    user_id: str
    username: str
    email: str
    first_name: str
    last_name: str
    full_name: str
    role: UserRole
    tenant_id: Optional[str]
    site_id: Optional[int]
    is_active: bool
    is_email_verified: bool
    last_login: Optional[datetime]
    password_changed_at: datetime
    created_by: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ===============================
# Entity Models
# ===============================


class TenantCreate(BaseModel):
    tenant_id: str
    name: str
    description: Optional[str] = None


class TenantUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class TenantStatusUpdate(BaseModel):
    is_active: bool


class TenantResponse(BaseModel):
    tenant_id: str
    name: str
    description: Optional[str] = None
    is_active: bool
    created_at: datetime


class SiteCreate(BaseModel):
    name: str
    location: Optional[str] = None


class SiteResponse(BaseModel):
    site_id: int
    tenant_id: str
    name: str
    location: Optional[str]
    created_at: datetime


class CameraCreate(BaseModel):
    name: str
    camera_type: CameraType = CameraType.RTSP
    rtsp_url: Optional[str] = None
    device_index: Optional[int] = None


class CameraResponse(BaseModel):
    camera_id: int
    tenant_id: str
    site_id: int
    name: str
    camera_type: CameraType
    rtsp_url: Optional[str]
    device_index: Optional[int]
    is_active: bool
    created_at: datetime


# ===============================
# Diagnostics & Device Models
# ===============================


class WebcamInfo(BaseModel):
    device_index: int
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[float] = None
    backend: Optional[str] = None
    is_working: bool
    frame_captured: bool
    in_use: bool = False
    in_use_by: Optional[str] = None


class WebcamListResponse(BaseModel):
    devices: List[WebcamInfo]
    source: str  # "workers" or "none"
    worker_sources: List[str]
    manual_input_required: bool
    message: str


class StaffCreate(BaseModel):
    name: str
    site_id: Optional[int] = None
    face_embedding: Optional[List[float]] = None


class StaffResponse(BaseModel):
    staff_id: int
    tenant_id: str
    name: str
    site_id: Optional[int]
    is_active: bool
    created_at: datetime


class StaffFaceImageCreate(BaseModel):
    image_data: str  # Base64 encoded image
    is_primary: bool = False


class StaffFaceImageBulkCreate(BaseModel):
    images: List[StaffFaceImageCreate]


class StaffFaceImageResponse(BaseModel):
    tenant_id: str
    image_id: str
    staff_id: int
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
    customer_id: int
    tenant_id: str
    name: Optional[str]
    gender: Optional[str]
    estimated_age_range: Optional[str]
    phone: Optional[str]
    email: Optional[str]
    first_seen: datetime
    last_seen: Optional[datetime]
    visit_count: int
    avatar_url: Optional[str] = None  # URL to first face image for avatar


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
    visit_session_id: str
    person_id: int
    person_type: str
    site_id: int
    camera_id: int
    timestamp: datetime
    first_seen: datetime
    last_seen: datetime
    visit_duration_seconds: Optional[int]
    detection_count: int
    confidence_score: float
    highest_confidence: Optional[float]
    image_path: Optional[str]


class VisitsPaginatedResponse(BaseModel):
    visits: List[VisitResponse]
    has_more: bool
    next_cursor: Optional[str]
    total_count: Optional[int] = None


class FaceEventResponse(BaseModel):
    match: str
    person_id: Optional[int]
    similarity: float
    visit_id: Optional[str]
    person_type: str
