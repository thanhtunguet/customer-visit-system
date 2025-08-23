import os
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.security import mint_jwt, get_current_user
from ..core.database import get_db  
from ..schemas import TokenRequest, TokenResponse

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
        
        # Dev auth: accept any non-empty values with system_admin role for now
        # TODO: Replace with proper user authentication after migration
        token = mint_jwt(
            sub=payload.username,
            role="system_admin",  # Default to system admin for dev
            tenant_id=payload.tenant_id
        )
        return TokenResponse(access_token=token)


@router.get("/me")
async def get_current_user_info(user: dict = Depends(get_current_user)):
    # Temporary fallback for dev when users table doesn't exist
    return {
        "user_id": "dev-admin",
        "username": user.get("sub", "dev-admin"),
        "email": "admin@dev.local",
        "first_name": "Dev",
        "last_name": "Admin",
        "full_name": "Dev Admin",
        "role": user.get("role", "system_admin"),
        "tenant_id": user.get("tenant_id"),
        "is_active": True,
        "is_email_verified": True,
        "last_login": None,
        "password_changed_at": "2023-01-01T00:00:00Z",
        "created_at": "2023-01-01T00:00:00Z",
        "updated_at": "2023-01-01T00:00:00Z"
    }


# ===============================
# User Management Endpoints (System Admin Only)
# ===============================
# NOTE: These endpoints require the users table to exist (run migration first)

@router.get("/users")
async def list_users(current_user: dict = Depends(get_current_user)):
    """Placeholder - requires database migration"""
    raise HTTPException(status_code=503, detail="User management not available - database migration required")


@router.post("/users")
async def create_user(current_user: dict = Depends(get_current_user)):
    """Placeholder - requires database migration"""
    raise HTTPException(status_code=503, detail="User management not available - database migration required")


# Additional user management endpoints temporarily disabled
# Uncomment and restore after running database migration