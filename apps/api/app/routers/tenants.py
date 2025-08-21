from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db_session, db
from ..core.security import get_current_user
from ..models.database import Tenant
from ..schemas import TenantCreate, TenantResponse

router = APIRouter(prefix="/v1", tags=["Tenant Management"])


@router.get("/tenants", response_model=List[TenantResponse])
async def list_tenants(
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    if user["role"] != "system_admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    
    await db.set_tenant_context(db_session, user["tenant_id"])
    
    result = await db_session.execute(select(Tenant))
    tenants = result.scalars().all()
    return tenants


@router.post("/tenants", response_model=TenantResponse)
async def create_tenant(
    tenant: TenantCreate,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    if user["role"] != "system_admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    
    new_tenant = Tenant(tenant_id=tenant.tenant_id, name=tenant.name)
    db_session.add(new_tenant)
    await db_session.commit()
    return new_tenant