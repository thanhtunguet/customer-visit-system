from __future__ import annotations

import time
from typing import Dict, Optional

import jwt
from fastapi import HTTPException, Depends, Header, Query

from .config import settings


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

