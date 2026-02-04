import hashlib
import secrets
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db_session
from ..core.security import (get_current_active_user, get_tenant_context,
                             mint_jwt, require_system_admin)
from ..models.database import ApiKey, User, UserRole
from ..schemas import (ApiKeyCreate, ApiKeyCreateResponse, ApiKeyResponse,
                       ApiKeyUpdate, TokenRequest, TokenResponse, UserCreate,
                       UserPasswordUpdate, UserResponse, UserUpdate,
                       ViewSwitchRequest)

router = APIRouter(prefix="/v1", tags=["Authentication"])


def _get_effective_tenant_id(user: User, tenant_context: Optional[str]) -> str:
    """Get effective tenant ID for API operations"""
    if user.role.value == "system_admin":
        # System admins can operate in any tenant context
        tenant_id = tenant_context or user.tenant_id
        if not tenant_id:
            raise HTTPException(
                status_code=400,
                detail="Please switch to a tenant view to manage API keys",
            )
        return tenant_id
    else:
        # Non-system admins can only operate in their own tenant
        if not user.tenant_id:
            raise HTTPException(
                status_code=400, detail="User must be assigned to a tenant"
            )
        return user.tenant_id


@router.post("/auth/token", response_model=TokenResponse)
async def issue_token(payload: TokenRequest, db: AsyncSession = Depends(get_db_session)):
    if payload.grant_type == "api_key":
        # API key authentication for workers
        if not payload.api_key:
            raise HTTPException(status_code=400, detail="Missing API key")

        # Hash the provided API key for lookup
        hashed_key = hashlib.sha256(payload.api_key.encode()).hexdigest()

        # Look up API key in database
        result = await db.execute(
            select(ApiKey).where(
                ApiKey.hashed_key == hashed_key,
                ApiKey.tenant_id == payload.tenant_id,
                ApiKey.is_active,
            )
        )
        api_key_record = result.scalar_one_or_none()

        if not api_key_record:
            raise HTTPException(status_code=401, detail="Invalid API key")

        # Check if API key has expired
        if api_key_record.expires_at and api_key_record.expires_at < datetime.utcnow():
            raise HTTPException(status_code=401, detail="API key has expired")

        # Update last_used timestamp
        api_key_record.last_used = datetime.utcnow()
        await db.commit()

        token = mint_jwt(
            sub="worker", role=api_key_record.role, tenant_id=api_key_record.tenant_id
        )
        return TokenResponse(access_token=token)

    else:
        # Username/password authentication
        if not (payload.username and payload.password):
            raise HTTPException(status_code=400, detail="Missing credentials")

        # Real user authentication
        result = await db.execute(
            select(User).where(User.username == payload.username)
        )
        user = result.scalar_one_or_none()
        if not user or not user.verify_password(payload.password):
            raise HTTPException(status_code=401, detail="Invalid username or password")

        if not user.is_active:
            raise HTTPException(status_code=401, detail="Account is disabled")

        # Update last login
        user.last_login = datetime.utcnow()
        await db.commit()

        # For system admins, allow optional tenant_id (global vs tenant view)
        # For tenant users, use their assigned tenant_id
        effective_tenant_id = user.tenant_id
        if user.role.value == "system_admin":
            effective_tenant_id = payload.tenant_id  # Can be None for global view
        elif payload.tenant_id and payload.tenant_id != user.tenant_id:
            raise HTTPException(
                status_code=403, detail="Cannot access different tenant"
            )

        token = mint_jwt(
            sub=user.username,
            role=user.role.value,
            tenant_id=effective_tenant_id,
            site_id=user.site_id,
        )
        return TokenResponse(access_token=token)


@router.post("/auth/switch-view", response_model=TokenResponse)
async def switch_view(
    payload: ViewSwitchRequest, user: User = Depends(get_current_active_user)
):
    """Switch view for system admins (global vs tenant view)"""
    # Only system admins can switch views
    if user.role.value != "system_admin":
        raise HTTPException(
            status_code=403, detail="Only system admins can switch views"
        )

    # Generate new token with target tenant context
    token = mint_jwt(
        sub=user.username,
        role=user.role.value,
        tenant_id=payload.target_tenant_id,
        site_id=user.site_id,
    )
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(user: User = Depends(get_current_active_user)):
    return user


@router.put("/me/password")
async def change_my_password(
    password_data: UserPasswordUpdate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_active_user),
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
    await db.commit()

    return {"message": "Password changed successfully"}


# ===============================
# User Management Endpoints (System Admin Only)
# ===============================


@router.get("/users", response_model=List[UserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db_session),
    admin: User = Depends(require_system_admin),
    skip: int = 0,
    limit: int = 100,
):
    """List all users (system admin only)"""
    result = await db.execute(select(User).offset(skip).limit(limit))
    users = result.scalars().all()
    return users


@router.post("/users", response_model=UserResponse)
async def create_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db_session),
    admin: User = Depends(require_system_admin),
):
    """Create a new user (system admin only)"""
    # Validate role and tenant_id combination
    if user_data.role != UserRole.SYSTEM_ADMIN and not user_data.tenant_id:
        raise HTTPException(
            status_code=400, detail="tenant_id is required for non-system admin users"
        )

    if user_data.role == UserRole.SYSTEM_ADMIN and user_data.tenant_id:
        raise HTTPException(
            status_code=400, detail="System admin users cannot be assigned to a tenant"
        )

    # Validate site_id for site managers
    if user_data.role == UserRole.SITE_MANAGER and not user_data.site_id:
        raise HTTPException(
            status_code=400, detail="site_id is required for site manager users"
        )

    if user_data.role != UserRole.SITE_MANAGER and user_data.site_id:
        raise HTTPException(
            status_code=400, detail="site_id can only be assigned to site manager users"
        )

    # Check if username or email already exists
    result = await db.execute(
        select(User).where(
            (User.username == user_data.username) | (User.email == user_data.email)
        )
    )
    existing_user = result.scalar_one_or_none()

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
        site_id=user_data.site_id,
        is_active=user_data.is_active,
        created_by=admin.user_id,
    )
    user.set_password(user_data.password)

    db.add(user)
    await db.commit()
    await db.refresh(user)

    return user


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db_session),
    admin: User = Depends(require_system_admin),
):
    """Get user by ID (system admin only)"""
    result = await db.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_data: UserUpdate,
    db: AsyncSession = Depends(get_db_session),
    admin: User = Depends(require_system_admin),
):
    """Update user (system admin only)"""
    result = await db.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Validate role and tenant_id combination if role is being changed
    if user_data.role is not None:
        if user_data.role != UserRole.SYSTEM_ADMIN and not (
            user_data.tenant_id or user.tenant_id
        ):
            raise HTTPException(
                status_code=400,
                detail="tenant_id is required for non-system admin users",
            )

        if user_data.role == UserRole.SYSTEM_ADMIN and (
            user_data.tenant_id or user.tenant_id
        ):
            user_data.tenant_id = None  # Clear tenant_id for system admin
            user_data.site_id = None  # Clear site_id for system admin

        # Validate site_id for site managers
        if user_data.role == UserRole.SITE_MANAGER and not (
            user_data.site_id or user.site_id
        ):
            raise HTTPException(
                status_code=400, detail="site_id is required for site manager users"
            )

        if user_data.role != UserRole.SITE_MANAGER and (
            user_data.site_id or user.site_id
        ):
            user_data.site_id = None  # Clear site_id for non-site-manager roles

    # Check for unique constraints if username or email is being changed
    if user_data.username and user_data.username != user.username:
        result = await db.execute(
            select(User).where(User.username == user_data.username)
        )
        existing = result.scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=400, detail="Username already exists")

    if user_data.email and user_data.email != user.email:
        result = await db.execute(select(User).where(User.email == user_data.email))
        existing = result.scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=400, detail="Email already exists")

    # Update fields
    for field, value in user_data.dict(exclude_unset=True).items():
        setattr(user, field, value)

    user.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(user)

    return user


@router.put("/users/{user_id}/password")
async def change_user_password(
    user_id: str,
    password_data: UserPasswordUpdate,
    db: AsyncSession = Depends(get_db_session),
    admin: User = Depends(require_system_admin),
):
    """Change user password (system admin only)"""
    result = await db.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # System admin can change any password without current password
    user.set_password(password_data.new_password)
    await db.commit()

    return {"message": "Password changed successfully"}


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    db: AsyncSession = Depends(get_db_session),
    admin: User = Depends(require_system_admin),
):
    """Delete user (system admin only)"""
    result = await db.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent deleting yourself
    if user.user_id == admin.user_id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    db.delete(user)
    await db.commit()

    return {"message": "User deleted successfully"}


@router.put("/users/{user_id}/toggle-status")
async def toggle_user_status(
    user_id: str,
    db: AsyncSession = Depends(get_db_session),
    admin: User = Depends(require_system_admin),
):
    """Toggle user active status (system admin only)"""
    result = await db.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent disabling yourself
    if user.user_id == admin.user_id:
        raise HTTPException(status_code=400, detail="Cannot disable your own account")

    user.is_active = not user.is_active
    user.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(user)

    return user


# ===============================
# API Key Management Endpoints
# ===============================


@router.get("/api-keys", response_model=List[ApiKeyResponse])
async def list_api_keys(
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_active_user),
    tenant_context: Optional[str] = Depends(get_tenant_context),
    skip: int = 0,
    limit: int = 100,
):
    """List API keys for current user's tenant"""
    tenant_id = _get_effective_tenant_id(user, tenant_context)

    result = await db.execute(
        select(ApiKey)
        .where(ApiKey.tenant_id == tenant_id)
        .offset(skip)
        .limit(limit)
    )
    api_keys = result.scalars().all()

    return api_keys


@router.post("/api-keys", response_model=ApiKeyCreateResponse)
async def create_api_key(
    api_key_data: ApiKeyCreate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_active_user),
    tenant_context: Optional[str] = Depends(get_tenant_context),
):
    """Create a new API key"""
    # Only tenant_admin and system_admin can create API keys
    if user.role.value not in ["tenant_admin", "system_admin"]:
        raise HTTPException(
            status_code=403, detail="Only tenant administrators can create API keys"
        )

    tenant_id = _get_effective_tenant_id(user, tenant_context)

    # Generate a secure random API key
    plain_key = secrets.token_urlsafe(32)  # 32 bytes = 256 bits of entropy
    hashed_key = hashlib.sha256(plain_key.encode()).hexdigest()

    # Create API key record
    api_key = ApiKey(
        tenant_id=tenant_id,
        hashed_key=hashed_key,
        name=api_key_data.name,
        role=api_key_data.role,
        expires_at=api_key_data.expires_at,
    )

    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)

    # Return response with plain text key (only time it's shown)
    return ApiKeyCreateResponse(
        key_id=api_key.key_id,
        tenant_id=api_key.tenant_id,
        name=api_key.name,
        role=api_key.role,
        api_key=plain_key,  # Plain text key - only shown once
        is_active=api_key.is_active,
        expires_at=api_key.expires_at,
        created_at=api_key.created_at,
    )


@router.get("/api-keys/{key_id}", response_model=ApiKeyResponse)
async def get_api_key(
    key_id: str,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_active_user),
    tenant_context: Optional[str] = Depends(get_tenant_context),
):
    """Get API key by ID"""
    tenant_id = _get_effective_tenant_id(user, tenant_context)

    result = await db.execute(
        select(ApiKey).where(
            ApiKey.key_id == key_id, ApiKey.tenant_id == tenant_id
        )
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    return api_key


@router.put("/api-keys/{key_id}", response_model=ApiKeyResponse)
async def update_api_key(
    key_id: str,
    api_key_data: ApiKeyUpdate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_active_user),
    tenant_context: Optional[str] = Depends(get_tenant_context),
):
    """Update API key"""
    # Only tenant_admin and system_admin can update API keys
    if user.role.value not in ["tenant_admin", "system_admin"]:
        raise HTTPException(
            status_code=403, detail="Only tenant administrators can update API keys"
        )

    tenant_id = _get_effective_tenant_id(user, tenant_context)

    result = await db.execute(
        select(ApiKey).where(
            ApiKey.key_id == key_id, ApiKey.tenant_id == tenant_id
        )
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    # Update fields
    for field, value in api_key_data.dict(exclude_unset=True).items():
        setattr(api_key, field, value)

    await db.commit()
    await db.refresh(api_key)

    return api_key


@router.delete("/api-keys/{key_id}")
async def delete_api_key(
    key_id: str,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_active_user),
    tenant_context: Optional[str] = Depends(get_tenant_context),
):
    """Delete API key"""
    # Only tenant_admin and system_admin can delete API keys
    if user.role.value not in ["tenant_admin", "system_admin"]:
        raise HTTPException(
            status_code=403, detail="Only tenant administrators can delete API keys"
        )

    tenant_id = _get_effective_tenant_id(user, tenant_context)

    result = await db.execute(
        select(ApiKey).where(
            ApiKey.key_id == key_id, ApiKey.tenant_id == tenant_id
        )
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    db.delete(api_key)
    await db.commit()

    return {"message": "API key deleted successfully"}
