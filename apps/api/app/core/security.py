from __future__ import annotations

import time
from typing import Optional

import jwt

from .config import settings


def mint_jwt(sub: str, role: str, tenant_id: str, ttl_sec: int = 3600) -> str:
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


def verify_jwt(token: str) -> dict:
    key: Optional[str] = settings.jwt_public_key or ("dev-key" if not settings.jwt_private_key else None)
    alg = "RS256" if settings.jwt_public_key else "HS256"
    return jwt.decode(token, key, algorithms=[alg], audience=settings.jwt_audience, options={"verify_aud": False})

