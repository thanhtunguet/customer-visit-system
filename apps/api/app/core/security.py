from __future__ import annotations

import time
from datetime import datetime
from typing import Dict, Optional, List
from functools import wraps

import jwt
from fastapi import HTTPException, Depends, Header, Query, Request
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from ..models.database import User, UserRole


def mint_jwt(sub: str, role: str, tenant_id: str, ttl_sec: int = 3600) -> str:
    """Create a JWT token with the given claims"""
    now = int(time.time())
    payload = {
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "sub": sub,
        "iat": now,
        "exp": now + ttl_sec,
        "role": role,
        "tenant_id": tenant_id,
    }
    if not settings.jwt_private_key:
        # Dev fallback: unsigned for local testing only
        return jwt.encode(payload, "dev-key", algorithm="HS256")
    return jwt.encode(payload, settings.jwt_private_key, algorithm="RS256")


def verify_jwt(token: str) -> Dict:
    """Verify and decode JWT token"""
    try:
        key: Optional[str] = settings.jwt_public_key or ("dev-key" if not settings.jwt_private_key else None)
        alg = "RS256" if settings.jwt_public_key else "HS256"
        payload = jwt.decode(
            token, 
            key, 
            algorithms=[alg], 
            audience=settings.jwt_audience, 
            options={"verify_aud": False}
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def get_current_user(authorization: Optional[str] = Header(None)) -> Dict:
    """FastAPI dependency to extract current user from JWT token"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header format")
    
    token = authorization.split(" ")[1]
    payload = verify_jwt(token)
    
    return {
        "sub": payload.get("sub"),
        "role": payload.get("role"),
        "tenant_id": payload.get("tenant_id"),
    }


def get_current_user_for_stream(
    authorization: Optional[str] = Header(None),
    access_token: Optional[str] = Query(None)
) -> Dict:
    """FastAPI dependency to extract current user from JWT token (supports both header and query param)"""
    token = None
    
    # Try Authorization header first
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
    # Fallback to query parameter
    elif access_token:
        token = access_token
    else:
        raise HTTPException(status_code=401, detail="Missing authentication token")
    
    payload = verify_jwt(token)
    
    return {
        "sub": payload.get("sub"),
        "role": payload.get("role"),
        "tenant_id": payload.get("tenant_id"),
    }


def require_roles(allowed_roles: List[UserRole]):
    """Decorator to require specific roles for accessing endpoints"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract user from kwargs (injected by get_current_user dependency)
            user_info = None
            for key, value in kwargs.items():
                if isinstance(value, dict) and "role" in value:
                    user_info = value
                    break
            
            if not user_info:
                raise HTTPException(status_code=401, detail="Authentication required")
            
            try:
                user_role = UserRole(user_info["role"])
                if user_role not in allowed_roles:
                    raise HTTPException(
                        status_code=403, 
                        detail=f"Access denied. Required roles: {[role.value for role in allowed_roles]}"
                    )
            except ValueError:
                raise HTTPException(status_code=401, detail="Invalid role")
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def get_current_active_user(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)) -> User:
    """Get current authenticated user from database"""
    if not current_user.get("sub"):
        raise HTTPException(status_code=401, detail="Invalid authentication")
    
    # For API key authentication (workers), create a virtual user object
    if current_user.get("sub") == "worker":
        # Return a virtual user for API key authentication
        user = User()
        user.user_id = "worker"
        user.username = "worker"
        user.role = UserRole.WORKER
        user.tenant_id = current_user.get("tenant_id")
        user.is_active = True
        return user
    
    # For regular user authentication, fetch from database
    user = db.query(User).filter(User.username == current_user["sub"]).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    if not user.is_active:
        raise HTTPException(status_code=401, detail="User account is disabled")
    
    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()
    
    return user


def require_system_admin(current_user: User = Depends(get_current_active_user)) -> User:
    """Dependency that requires system admin role"""
    if current_user.role != UserRole.SYSTEM_ADMIN:
        raise HTTPException(status_code=403, detail="System administrator access required")
    return current_user


def get_tenant_context(request: Request) -> Optional[str]:
    """Get tenant context from request state (set by tenant_context_middleware)"""
    return getattr(request.state, 'tenant_id', None)


def require_tenant_admin_or_above(current_user: User = Depends(get_current_active_user)) -> User:
    """Dependency that requires tenant admin or system admin role"""
    if current_user.role not in [UserRole.SYSTEM_ADMIN, UserRole.TENANT_ADMIN]:
        raise HTTPException(status_code=403, detail="Administrative access required")
    return current_user

