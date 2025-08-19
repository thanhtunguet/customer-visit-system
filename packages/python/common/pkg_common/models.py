from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, HttpUrl


class FaceDetectedEvent(BaseModel):
    tenant_id: str
    site_id: str
    camera_id: str
    timestamp: datetime
    embedding: List[float] = Field(min_length=512, max_length=512)
    bbox: List[float] = Field(min_length=4, max_length=4)
    snapshot_url: Optional[HttpUrl] | None = None
    is_staff_local: bool = False


class VisitRecord(BaseModel):
    tenant_id: str
    site_id: str
    person_id: str
    timestamp: datetime
    confidence: float
    image_path: Optional[str] | None = None


class CustomerProfile(BaseModel):
    tenant_id: str
    customer_id: str
    name: Optional[str] | None = None
    gender: Optional[str] | None = Field(default=None)
    first_seen: datetime
    last_seen: Optional[datetime] | None = None

