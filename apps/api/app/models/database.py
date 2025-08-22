from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import Column, String, Boolean, DateTime, Float, Integer, BigInteger, ForeignKey, ForeignKeyConstraint, Text, Index, Enum
import enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid

Base = declarative_base()


class CameraType(enum.Enum):
    RTSP = "rtsp"
    WEBCAM = "webcam"


class Tenant(Base):
    __tablename__ = "tenants"
    
    tenant_id = Column(String(64), primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    sites = relationship("Site", back_populates="tenant", cascade="all, delete-orphan")
    staff = relationship("Staff", back_populates="tenant", cascade="all, delete-orphan")
    customers = relationship("Customer", back_populates="tenant", cascade="all, delete-orphan")
    api_keys = relationship("ApiKey", back_populates="tenant", cascade="all, delete-orphan")


class Site(Base):
    __tablename__ = "sites"
    
    site_id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(String(64), ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    location = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="sites")
    cameras = relationship("Camera", back_populates="site", cascade="all, delete-orphan")


class Camera(Base):
    __tablename__ = "cameras"
    
    camera_id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(String(64), nullable=False)
    site_id = Column(BigInteger, nullable=False)
    name = Column(String(255), nullable=False)
    camera_type = Column(Enum(CameraType), default=CameraType.RTSP, nullable=False)
    rtsp_url = Column(Text)  # For RTSP cameras
    device_index = Column(Integer)  # For webcam cameras (e.g., 0, 1, 2)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Foreign key constraints
    __table_args__ = (
        ForeignKeyConstraint(['tenant_id'], ['tenants.tenant_id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['site_id'], ['sites.site_id'], ondelete='CASCADE'),
    )
    
    # Relationships
    site = relationship("Site", back_populates="cameras")


class Staff(Base):
    __tablename__ = "staff"
    
    staff_id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(String(64), ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    site_id = Column(BigInteger)
    is_active = Column(Boolean, default=True, nullable=False)
    face_embedding = Column(Text)  # Legacy field - kept for backwards compatibility
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="staff")
    face_images = relationship("StaffFaceImage", cascade="all, delete-orphan")

class StaffFaceImage(Base):
    __tablename__ = "staff_face_images"
    
    tenant_id = Column(String(64), ForeignKey("tenants.tenant_id", ondelete="CASCADE"), primary_key=True)
    image_id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    staff_id = Column(BigInteger, nullable=False)
    image_path = Column(String(500), nullable=False)
    face_landmarks = Column(Text)  # JSON serialized landmarks (5-point)
    face_embedding = Column(Text)  # JSON serialized 512-D vector  
    image_hash = Column(String(64), nullable=True)  # SHA-256 hash for duplicate detection
    is_primary = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships 
    tenant = relationship("Tenant", overlaps="face_images")
    
    __table_args__ = (
        ForeignKeyConstraint(['tenant_id'], ['tenants.tenant_id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['staff_id'], ['staff.staff_id'], ondelete='CASCADE'),
        Index('idx_staff_face_images_staff_id', 'tenant_id', 'staff_id'),
        Index('idx_staff_face_images_primary', 'tenant_id', 'is_primary'),
        Index('idx_staff_face_images_hash', 'tenant_id', 'staff_id', 'image_hash', unique=True),
    )


class Customer(Base):
    __tablename__ = "customers"
    
    customer_id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(String(64), ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255))
    gender = Column(String(16))  # male, female, unknown
    estimated_age_range = Column(String(32))
    phone = Column(String(20))
    email = Column(String(255))
    first_seen = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen = Column(DateTime)
    visit_count = Column(Integer, default=0, nullable=False)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="customers")
    
    __table_args__ = (
        Index('idx_customers_last_seen', 'tenant_id', 'last_seen'),
    )


class Visit(Base):
    __tablename__ = "visits"
    
    tenant_id = Column(String(64), primary_key=True)
    visit_id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    person_id = Column(BigInteger, nullable=False)
    person_type = Column(String(16), nullable=False)  # staff, customer
    site_id = Column(BigInteger, nullable=False)
    camera_id = Column(BigInteger, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    confidence_score = Column(Float, nullable=False)
    face_embedding = Column(Text)  # JSON serialized vector
    image_path = Column(Text)
    bbox_x = Column(Float)
    bbox_y = Column(Float)
    bbox_w = Column(Float)
    bbox_h = Column(Float)
    
    __table_args__ = (
        Index('idx_visits_timestamp', 'tenant_id', 'timestamp'),
        Index('idx_visits_person', 'tenant_id', 'person_id', 'timestamp'),
        Index('idx_visits_site', 'tenant_id', 'site_id', 'timestamp'),
    )


class ApiKey(Base):
    __tablename__ = "api_keys"
    
    key_id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(64), ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False)
    hashed_key = Column(Text, nullable=False)
    name = Column(String(255), nullable=False)
    role = Column(String(32), default="worker", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    last_used = Column(DateTime)
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="api_keys")