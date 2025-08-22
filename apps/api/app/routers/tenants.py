from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db_session, db
from ..core.security import get_current_user
from ..models.database import Tenant
from ..schemas import TenantCreate, TenantUpdate, TenantStatusUpdate, TenantResponse

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
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only system administrators can create tenants")
    
    # Check if tenant already exists
    result = await db_session.execute(
        select(Tenant).where(Tenant.tenant_id == tenant.tenant_id)
    )
    existing_tenant = result.scalar_one_or_none()
    if existing_tenant:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, 
            detail=f"Tenant with ID '{tenant.tenant_id}' already exists"
        )
    
    new_tenant = Tenant(
        tenant_id=tenant.tenant_id, 
        name=tenant.name,
        description=tenant.description,
        is_active=True
    )
    db_session.add(new_tenant)
    await db_session.commit()
    await db_session.refresh(new_tenant)
    return new_tenant


@router.get("/tenants/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: str,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    if user["role"] != "system_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only system administrators can view tenants")
    
    result = await db_session.execute(
        select(Tenant).where(Tenant.tenant_id == tenant_id)
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    
    return tenant


@router.put("/tenants/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: str,
    tenant_update: TenantUpdate,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    if user["role"] != "system_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only system administrators can update tenants")
    
    result = await db_session.execute(
        select(Tenant).where(Tenant.tenant_id == tenant_id)
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    
    # Update only provided fields
    update_data = tenant_update.dict(exclude_unset=True)
    if update_data:
        await db_session.execute(
            update(Tenant)
            .where(Tenant.tenant_id == tenant_id)
            .values(**update_data)
        )
        await db_session.commit()
        await db_session.refresh(tenant)
    
    return tenant


@router.patch("/tenants/{tenant_id}/status", response_model=TenantResponse)
async def toggle_tenant_status(
    tenant_id: str,
    status_update: TenantStatusUpdate,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    if user["role"] != "system_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only system administrators can modify tenant status")
    
    result = await db_session.execute(
        select(Tenant).where(Tenant.tenant_id == tenant_id)
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    
    # Update tenant status
    await db_session.execute(
        update(Tenant)
        .where(Tenant.tenant_id == tenant_id)
        .values(is_active=status_update.is_active)
    )
    await db_session.commit()
    await db_session.refresh(tenant)
    
    return tenant


@router.delete("/tenants/{tenant_id}")
async def delete_tenant(
    tenant_id: str,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    if user["role"] != "system_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only system administrators can delete tenants")
    
    result = await db_session.execute(
        select(Tenant).where(Tenant.tenant_id == tenant_id)
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    
    # Check if tenant has active dependencies (sites, staff, customers)
    # This is handled by CASCADE DELETE in the database, but we can add business logic here if needed
    
    await db_session.delete(tenant)
    await db_session.commit()
    
    return {"message": f"Tenant '{tenant_id}' deleted successfully"}