import os

from fastapi import APIRouter, Depends, HTTPException

from ..core.security import mint_jwt, get_current_user
from ..schemas import TokenRequest, TokenResponse

router = APIRouter(prefix="/v1", tags=["Authentication"])


@router.post("/auth/token", response_model=TokenResponse)
async def issue_token(payload: TokenRequest):
    if payload.grant_type == "api_key":
        if payload.api_key != os.getenv("WORKER_API_KEY", "dev-api-key"):
            raise HTTPException(status_code=401, detail="Invalid API key")
    else:
        if not (payload.username and payload.password):
            raise HTTPException(status_code=400, detail="Missing credentials")
        # Dev auth: accept any non-empty values
    
    token = mint_jwt(
        sub=payload.username or "worker",
        role=payload.role,
        tenant_id=payload.tenant_id
    )
    return TokenResponse(access_token=token)


@router.get("/me")
async def get_current_user_info(user: dict = Depends(get_current_user)):
    return user