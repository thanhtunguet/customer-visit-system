from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import db, get_db_session
from ..core.security import get_current_user
from ..models.database import (ApiKey, Camera, Customer, Site, Staff,
                               StaffFaceImage, Tenant, UserRole, Visit)
from ..schemas import (TenantCreate, TenantResponse, TenantStatusUpdate,
                       TenantUpdate)

router = APIRouter(prefix="/v1", tags=["Tenant Management"])


@router.get("/tenants", response_model=List[TenantResponse])
async def list_tenants(
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    if user["role"] != UserRole.SYSTEM_ADMIN.value:
        raise HTTPException(status_code=403, detail="Forbidden")

    await db.set_tenant_context(db_session, user["tenant_id"])

    result = await db_session.execute(select(Tenant))
    tenants = result.scalars().all()
    return tenants


@router.post("/tenants", response_model=TenantResponse)
async def create_tenant(
    tenant: TenantCreate,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    if user["role"] != UserRole.SYSTEM_ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only system administrators can create tenants",
        )

    # Check if tenant already exists
    result = await db_session.execute(
        select(Tenant).where(Tenant.tenant_id == tenant.tenant_id)
    )
    existing_tenant = result.scalar_one_or_none()
    if existing_tenant:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tenant with ID '{tenant.tenant_id}' already exists",
        )

    new_tenant = Tenant(
        tenant_id=tenant.tenant_id,
        name=tenant.name,
        description=tenant.description,
        is_active=True,
    )
    db_session.add(new_tenant)
    await db_session.commit()
    await db_session.refresh(new_tenant)
    return new_tenant


@router.get("/tenants/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: str,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    if user["role"] != UserRole.SYSTEM_ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only system administrators can view tenants",
        )

    result = await db_session.execute(
        select(Tenant).where(Tenant.tenant_id == tenant_id)
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found"
        )

    return tenant


@router.put("/tenants/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: str,
    tenant_update: TenantUpdate,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    if user["role"] != UserRole.SYSTEM_ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only system administrators can update tenants",
        )

    result = await db_session.execute(
        select(Tenant).where(Tenant.tenant_id == tenant_id)
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found"
        )

    # Update only provided fields
    update_data = tenant_update.dict(exclude_unset=True)
    if update_data:
        await db_session.execute(
            update(Tenant).where(Tenant.tenant_id == tenant_id).values(**update_data)
        )
        await db_session.commit()
        await db_session.refresh(tenant)

    return tenant


@router.patch("/tenants/{tenant_id}/status", response_model=TenantResponse)
async def toggle_tenant_status(
    tenant_id: str,
    status_update: TenantStatusUpdate,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    if user["role"] != UserRole.SYSTEM_ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only system administrators can modify tenant status",
        )

    result = await db_session.execute(
        select(Tenant).where(Tenant.tenant_id == tenant_id)
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found"
        )

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
    db_session: AsyncSession = Depends(get_db_session),
):
    if user["role"] != UserRole.SYSTEM_ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only system administrators can delete tenants",
        )

    result = await db_session.execute(
        select(Tenant).where(Tenant.tenant_id == tenant_id)
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found"
        )

    # Check if tenant has dependencies that prevent deletion

    # Check for sites
    sites_result = await db_session.execute(
        select(Site).where(Site.tenant_id == tenant_id)
    )
    sites = sites_result.scalars().all()

    if sites:
        # Check if any site has cameras, staff, or customers
        site_ids = [site.site_id for site in sites]

        # Check for cameras in any site
        cameras_result = await db_session.execute(
            select(func.count(Camera.camera_id)).where(Camera.site_id.in_(site_ids))
        )
        camera_count = cameras_result.scalar()

        if camera_count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot delete tenant. Tenant has {len(sites)} site(s) with {camera_count} camera(s). Remove all cameras from sites first.",
            )

    # Check for staff directly associated with tenant
    staff_result = await db_session.execute(
        select(func.count(Staff.staff_id)).where(Staff.tenant_id == tenant_id)
    )
    staff_count = staff_result.scalar()

    if staff_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete tenant. Tenant has {staff_count} staff member(s). Remove all staff first.",
        )

    # Check for staff face images
    staff_face_images_result = await db_session.execute(
        select(func.count(StaffFaceImage.image_id)).where(
            StaffFaceImage.tenant_id == tenant_id
        )
    )
    staff_face_images_count = staff_face_images_result.scalar()

    if staff_face_images_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete tenant. Tenant has {staff_face_images_count} staff face image(s). Remove all staff face images first.",
        )

    # Check for customers
    customers_result = await db_session.execute(
        select(func.count(Customer.customer_id)).where(Customer.tenant_id == tenant_id)
    )
    customer_count = customers_result.scalar()

    if customer_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete tenant. Tenant has {customer_count} customer(s). All customer data must be removed first.",
        )

    # Check for visits
    visits_result = await db_session.execute(
        select(func.count(Visit.visit_id)).where(Visit.tenant_id == tenant_id)
    )
    visit_count = visits_result.scalar()

    if visit_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete tenant. Tenant has {visit_count} visit record(s). All visit data must be removed first.",
        )

    # Check for API keys
    api_keys_result = await db_session.execute(
        select(func.count(ApiKey.key_id)).where(ApiKey.tenant_id == tenant_id)
    )
    api_key_count = api_keys_result.scalar()

    if api_key_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete tenant. Tenant has {api_key_count} API key(s). Remove all API keys first.",
        )

    # If we reach here, tenant has no dependencies and can be safely deleted
    await db_session.delete(tenant)
    await db_session.commit()

    return {"message": f"Tenant '{tenant_id}' deleted successfully"}
