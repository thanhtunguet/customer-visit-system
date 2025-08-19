from __future__ import annotations

import os
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .core.config import settings
from .core.middleware import tenant_context_middleware
from .core.security import mint_jwt

app = FastAPI(title="Face API", version="0.1.0", openapi_url="/v1/openapi.json")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.middleware("http")(tenant_context_middleware)


class TokenRequest(BaseModel):
    grant_type: str = "password"  # or "api_key"
    username: Optional[str] = None
    password: Optional[str] = None
    api_key: Optional[str] = None
    tenant_id: str
    role: str = "worker"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@app.get("/v1/health")
async def health():
    return {"status": "ok", "env": settings.env}


@app.post("/v1/auth/token", response_model=TokenResponse)
async def issue_token(payload: TokenRequest):
    if payload.grant_type == "api_key":
        if payload.api_key != os.getenv("WORKER_API_KEY", "dev-api-key"):
            raise HTTPException(status_code=401, detail="invalid api key")
    else:
        if not (payload.username and payload.password):
            raise HTTPException(status_code=400, detail="missing credentials")
        # Dev auth: accept any non-empty values
    token = mint_jwt(sub=payload.username or "worker", role=payload.role, tenant_id=payload.tenant_id)
    return TokenResponse(access_token=token)


# Minimal in-memory Tenants CRUD for bootstrap
TENANTS: dict[str, dict] = {}


class Tenant(BaseModel):
    tenant_id: str
    name: str


@app.get("/v1/tenants")
async def list_tenants(request: Request):
    role = getattr(request.state, "role", None)
    if role != "system_admin":
        raise HTTPException(status_code=403, detail="forbidden")
    return list(TENANTS.values())


@app.post("/v1/tenants")
async def create_tenant(tenant: Tenant, request: Request):
    role = getattr(request.state, "role", None)
    if role != "system_admin":
        raise HTTPException(status_code=403, detail="forbidden")
    TENANTS[tenant.tenant_id] = tenant.model_dump()
    return tenant


@app.get("/v1/me")
async def me(request: Request):
    return {
        "tenant_id": getattr(request.state, "tenant_id", None),
        "role": getattr(request.state, "role", None),
        "sub": getattr(request.state, "sub", None),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.host, port=settings.port)

# --- Events (bootstrap stub) ---
class FaceDetectedEvent(BaseModel):
    tenant_id: str
    site_id: str
    camera_id: str
    timestamp: str
    embedding: list[float]
    bbox: list[float]
    snapshot_url: str | None = None
    is_staff_local: bool = False


@app.post("/v1/events/face")
async def ingest_face(evt: FaceDetectedEvent, request: Request):
    # Validate tenant in request context
    tenant_id = getattr(request.state, "tenant_id", None) or evt.tenant_id
    # Return mock match result
    return {
        "tenant_id": tenant_id,
        "matched": not evt.is_staff_local,
        "candidate": {
            "person_id": "p-0001",
            "confidence": 0.42,
        },
    }
