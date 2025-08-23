import os
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.security import (
    mint_jwt, 
    get_current_user, 
    get_current_active_user, 
    require_system_admin
)
from ..core.database import get_db
from ..models.database import User, UserRole
from ..schemas import (
    TokenRequest, 
    TokenResponse, 
    UserCreate, 
    UserUpdate, 
    UserPasswordUpdate, 
    UserResponse
)

router = APIRouter(prefix="/v1", tags=["Authentication"])


@router.post("/auth/token", response_model=TokenResponse)
async def issue_token(payload: TokenRequest, db: Session = Depends(get_db)):
    if payload.grant_type == "api_key":
        # API key authentication for workers
        if payload.api_key != os.getenv("WORKER_API_KEY", "dev-api-key"):
            raise HTTPException(status_code=401, detail="Invalid API key")
        
        token = mint_jwt(
            sub="worker",
            role=payload.role,
            tenant_id=payload.tenant_id
        )
        return TokenResponse(access_token=token)
    
    else:
        # Username/password authentication
        if not (payload.username and payload.password):
            raise HTTPException(status_code=400, detail="Missing credentials")
        
        # Real user authentication
        user = db.query(User).filter(User.username == payload.username).first()
        if not user or not user.verify_password(payload.password):
            raise HTTPException(status_code=401, detail="Invalid username or password")
        
        if not user.is_active:
            raise HTTPException(status_code=401, detail="Account is disabled")
        
        # Update last login
        user.last_login = datetime.utcnow()
        db.commit()
        
        token = mint_jwt(
            sub=user.username,
            role=user.role.value,
            tenant_id=user.tenant_id or payload.tenant_id
        )
        return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(user: User = Depends(get_current_active_user)):
    return user

@router.put("/me/password")
async def change_my_password(
    password_data: UserPasswordUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user)
):
    """Change current user's password (requires current password)"""
    # Verify current password
    if not password_data.current_password:
        raise HTTPException(status_code=400, detail="Current password is required")
    
    if not user.verify_password(password_data.current_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    
    # Set new password
    user.set_password(password_data.new_password)
    user.updated_at = datetime.utcnow()
    db.commit()
    
    return {"message": "Password changed successfully"}


# ===============================
# User Management Endpoints (System Admin Only)
# ===============================

@router.get("/users", response_model=List[UserResponse])
async def list_users(
    db: Session = Depends(get_db),
    admin: User = Depends(require_system_admin),
    skip: int = 0,
    limit: int = 100
):
    """List all users (system admin only)"""
    users = db.query(User).offset(skip).limit(limit).all()
    return users


@router.post("/users", response_model=UserResponse)
async def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_system_admin)
):
    """Create a new user (system admin only)"""
    # Validate role and tenant_id combination
    if user_data.role != UserRole.SYSTEM_ADMIN and not user_data.tenant_id:
        raise HTTPException(
            status_code=400, 
            detail="tenant_id is required for non-system admin users"
        )
    
    if user_data.role == UserRole.SYSTEM_ADMIN and user_data.tenant_id:
        raise HTTPException(
            status_code=400, 
            detail="System admin users cannot be assigned to a tenant"
        )
    
    # Check if username or email already exists
    existing_user = db.query(User).filter(
        (User.username == user_data.username) | (User.email == user_data.email)
    ).first()
    
    if existing_user:
        raise HTTPException(status_code=400, detail="Username or email already exists")
    
    # Create new user
    user = User(
        username=user_data.username,
        email=user_data.email,
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        role=user_data.role,
        tenant_id=user_data.tenant_id,
        is_active=user_data.is_active,
        created_by=admin.user_id
    )
    user.set_password(user_data.password)
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return user


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_system_admin)
):
    """Get user by ID (system admin only)"""
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_system_admin)
):
    """Update user (system admin only)"""
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Validate role and tenant_id combination if role is being changed
    if user_data.role is not None:
        if user_data.role != UserRole.SYSTEM_ADMIN and not (user_data.tenant_id or user.tenant_id):
            raise HTTPException(
                status_code=400, 
                detail="tenant_id is required for non-system admin users"
            )
        
        if user_data.role == UserRole.SYSTEM_ADMIN and (user_data.tenant_id or user.tenant_id):
            user_data.tenant_id = None  # Clear tenant_id for system admin
    
    # Check for unique constraints if username or email is being changed
    if user_data.username and user_data.username != user.username:
        existing = db.query(User).filter(User.username == user_data.username).first()
        if existing:
            raise HTTPException(status_code=400, detail="Username already exists")
    
    if user_data.email and user_data.email != user.email:
        existing = db.query(User).filter(User.email == user_data.email).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already exists")
    
    # Update fields
    for field, value in user_data.dict(exclude_unset=True).items():
        setattr(user, field, value)
    
    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)
    
    return user


@router.put("/users/{user_id}/password")
async def change_user_password(
    user_id: str,
    password_data: UserPasswordUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_system_admin)
):
    """Change user password (system admin only)"""
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # System admin can change any password without current password
    user.set_password(password_data.new_password)
    db.commit()
    
    return {"message": "Password changed successfully"}


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_system_admin)
):
    """Delete user (system admin only)"""
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent deleting yourself
    if user.user_id == admin.user_id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    
    db.delete(user)
    db.commit()
    
    return {"message": "User deleted successfully"}


@router.put("/users/{user_id}/toggle-status")
async def toggle_user_status(
    user_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_system_admin)
):
    """Toggle user active status (system admin only)"""
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent disabling yourself
    if user.user_id == admin.user_id:
        raise HTTPException(status_code=400, detail="Cannot disable your own account")
    
    user.is_active = not user.is_active
    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)
    
    return user
