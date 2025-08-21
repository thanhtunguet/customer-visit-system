from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db_session, db
from ..core.security import get_current_user
from ..models.database import Site
from ..schemas import SiteCreate, SiteResponse

router = APIRouter(prefix="/v1", tags=["Site Management"])


@router.get("/sites", response_model=List[SiteResponse])
async def list_sites(
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    await db.set_tenant_context(db_session, user["tenant_id"])
    
    result = await db_session.execute(
        select(Site).where(Site.tenant_id == user["tenant_id"])
    )
    sites = result.scalars().all()
    return sites


@router.post("/sites", response_model=SiteResponse)
async def create_site(
    site: SiteCreate,
    user: dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    await db.set_tenant_context(db_session, user["tenant_id"])
    
    new_site = Site(
        tenant_id=user["tenant_id"],
        site_id=site.site_id,
        name=site.name,
        location=site.location
    )
    db_session.add(new_site)
    await db_session.commit()
    return new_site