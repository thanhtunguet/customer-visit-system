from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import Column, String, Boolean, DateTime, Float, Integer, BigInteger, ForeignKey, ForeignKeyConstraint, Text, Index, Enum, JSON, TIMESTAMP
from sqlalchemy.sql import func
import enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
from passlib.context import CryptContext

# Enum definitions
class CameraType(enum.Enum):
    RTSP = "rtsp"
    WEBCAM = "webcam"


class UserRole(enum.Enum):
    SYSTEM_ADMIN = "system_admin"
    TENANT_ADMIN = "tenant_admin"
    SITE_MANAGER = "site_manager"
    WORKER = "worker"


# Password context for hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    
    user_id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(255), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    first_name = Column(String(255), nullable=False)
    last_name = Column(String(255), nullable=False)
    password_hash = Column(Text, nullable=False)
    role = Column(Enum(UserRole), nullable=False)
    tenant_id = Column(String(64), ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=True)  # Null for system_admin
    is_active = Column(Boolean, default=True, nullable=False)
    is_email_verified = Column(Boolean, default=False, nullable=False)
    last_login = Column(DateTime, nullable=True)
    password_changed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_by = Column(String(64), ForeignKey("users.user_id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    tenant = relationship("Tenant", backref="users")
    creator = relationship("User", remote_side=[user_id], backref="created_users")
    
    __table_args__ = (
        Index('idx_users_username', 'username'),
        Index('idx_users_email', 'email'),
        Index('idx_users_role', 'role'),
        Index('idx_users_tenant_id', 'tenant_id'),
    )
    
    def set_password(self, password: str) -> None:
        """Hash and set user password"""
        self.password_hash = pwd_context.hash(password)
        self.password_changed_at = datetime.utcnow()
    
    def verify_password(self, password: str) -> bool:
        """Verify user password"""
        return pwd_context.verify(password, self.password_hash)
    
    @property
    def full_name(self) -> str:
        """Get full name"""
        return f"{self.first_name} {self.last_name}"
    
    def can_access_tenant(self, tenant_id: str) -> bool:
        """Check if user can access a specific tenant"""
        if self.role == UserRole.SYSTEM_ADMIN:
            return True
        return self.tenant_id == tenant_id


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
    
    # New fields for enhanced camera management
    caps = Column(JSON, nullable=True)  # Camera capabilities: {"codec":"h264","res":"1920x1080","fps":25}
    last_probe_at = Column(TIMESTAMP(timezone=True), nullable=True)
    last_state_change_at = Column(TIMESTAMP(timezone=True), nullable=True)
    
    # Foreign key constraints
    __table_args__ = (
        ForeignKeyConstraint(['tenant_id'], ['tenants.tenant_id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['site_id'], ['sites.site_id'], ondelete='CASCADE'),
    )
    
    # Relationships
    site = relationship("Site", back_populates="cameras")
    session = relationship("CameraSession", back_populates="camera", uselist=False)

class CameraSession(Base):
    """
    Camera session model for tracking camera assignments with lease-based delegation
    
    States:
    - PENDING: Camera available but not assigned
    - ACTIVE: Camera assigned and worker confirmed active
    - PAUSED: Temporarily paused (worker issue, etc.)
    - ORPHANED: Worker disconnected but still within grace period
    - TERMINATED: Session ended, camera available for reassignment
    """
    __tablename__ = 'camera_sessions'
    
    camera_id = Column(BigInteger, ForeignKey('cameras.camera_id'), primary_key=True)
    tenant_id = Column(String(64), ForeignKey('tenants.tenant_id'), nullable=False)
    site_id = Column(BigInteger, ForeignKey('sites.site_id'), nullable=False)
    worker_id = Column(String, nullable=True)
    generation = Column(BigInteger, nullable=False, default=0)
    state = Column(String(20), nullable=False, default='PENDING')
    lease_expires_at = Column(TIMESTAMP(timezone=True), nullable=True)
    reason = Column(Text, nullable=True)
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    camera = relationship("Camera", back_populates="session")
    tenant = relationship("Tenant")
    site = relationship("Site")
    
    def __repr__(self):
        return f"<CameraSession(camera_id={self.camera_id}, worker_id={self.worker_id}, state={self.state}, generation={self.generation})>"
    
    def to_dict(self):
        return {
            'camera_id': self.camera_id,
            'tenant_id': self.tenant_id,
            'site_id': self.site_id,
            'worker_id': self.worker_id,
            'generation': self.generation,
            'state': self.state,
            'lease_expires_at': self.lease_expires_at.isoformat() if self.lease_expires_at else None,
            'reason': self.reason,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Staff(Base):
    __tablename__ = "staff"
    
    staff_id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(String(64), ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    site_id = Column(BigInteger, ForeignKey("sites.site_id"), nullable=True)
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


class CustomerFaceImage(Base):
    __tablename__ = "customer_face_images"
    
    image_id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(String(64), ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False)
    customer_id = Column(BigInteger, nullable=False)
    image_path = Column(String(500), nullable=False)
    confidence_score = Column(Float, nullable=False)
    quality_score = Column(Float, nullable=True)
    face_bbox = Column(JSON, nullable=True)  # [x, y, w, h]
    embedding = Column(JSON, nullable=True)  # Face embedding vector
    image_hash = Column(String(64), nullable=True)  # For duplicate detection
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    visit_id = Column(String(64), nullable=True)  # Reference to source visit
    detection_metadata = Column(JSON, nullable=True)  # Additional metadata (detector, landmarks, etc.)
    
    # Relationships
    tenant = relationship("Tenant")
    
    __table_args__ = (
        ForeignKeyConstraint(['customer_id'], ['customers.customer_id'], ondelete='CASCADE'),
        Index('idx_customer_face_images_tenant_customer', 'tenant_id', 'customer_id'),
        Index('idx_customer_face_images_confidence', 'tenant_id', 'customer_id', 'confidence_score'),
        Index('idx_customer_face_images_hash', 'tenant_id', 'image_hash'),
        Index('idx_customer_face_images_created', 'tenant_id', 'customer_id', 'created_at'),
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
    
    # Visit session fields for deduplication
    visit_session_id = Column(String(64), nullable=False, default=lambda: str(uuid.uuid4()))
    first_seen = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_seen = Column(DateTime, nullable=False, default=datetime.utcnow)
    visit_duration_seconds = Column(Integer, nullable=True, default=0)
    detection_count = Column(Integer, nullable=False, default=1)
    highest_confidence = Column(Float, nullable=True)
    
    __table_args__ = (
        Index('idx_visits_timestamp', 'tenant_id', 'timestamp'),
        Index('idx_visits_person', 'tenant_id', 'person_id', 'timestamp'),
        Index('idx_visits_site', 'tenant_id', 'site_id', 'timestamp'),
        Index('idx_visits_session', 'tenant_id', 'visit_session_id'),
        Index('idx_visits_person_time', 'tenant_id', 'person_id', 'last_seen'),
    )


class Worker(Base):
    __tablename__ = "workers"
    
    worker_id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(64), ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False)
    hostname = Column(String(255), nullable=False)
    ip_address = Column(String(45), nullable=True)  # Support both IPv4 and IPv6
    worker_name = Column(String(255), nullable=False)
    worker_version = Column(String(32), nullable=True)
    capabilities = Column(Text, nullable=True)  # JSON string of worker capabilities
    status = Column(String(32), default="offline", nullable=False)  # online, offline, error, maintenance
    site_id = Column(BigInteger, nullable=True)  # Optional site assignment
    camera_id = Column(BigInteger, nullable=True)  # Optional camera assignment
    last_heartbeat = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    error_count = Column(Integer, default=0, nullable=False)
    total_faces_processed = Column(BigInteger, default=0, nullable=False)
    registration_time = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    tenant = relationship("Tenant")
    
    __table_args__ = (
        Index('idx_workers_tenant_status', 'tenant_id', 'status'),
        Index('idx_workers_heartbeat', 'tenant_id', 'last_heartbeat'),
        Index('idx_workers_hostname', 'tenant_id', 'hostname'),
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