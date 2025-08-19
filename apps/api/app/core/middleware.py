from __future__ import annotations

from typing import Callable

from fastapi import Request

from .config import settings
from .security import verify_jwt


async def tenant_context_middleware(request: Request, call_next: Callable):
    tenant_id = request.headers.get(settings.tenant_header)
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        try:
            claims = verify_jwt(token)
            tenant_id = tenant_id or claims.get("tenant_id")
            request.state.role = claims.get("role")
            request.state.sub = claims.get("sub")
        except Exception:
            pass
    request.state.tenant_id = tenant_id
    response = await call_next(request)
    return response

