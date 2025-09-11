"""
Integration tests for lease-based camera delegation
Tests the GPT Plan implementation
"""

import asyncio
from datetime import datetime, timedelta

import pytest
from apps.api.app.core.database import get_async_session
from apps.api.app.models.database import Camera, CameraSession, Site, Tenant
from apps.api.app.services.assignment_service import SessionState, assignment_service


@pytest.mark.asyncio
async def test_lease_based_assignment():
    """Test basic lease-based assignment flow"""

    # Setup test data
    async with get_async_session() as db:
        # Create test tenant and site
        tenant = Tenant(
            tenant_id="test_tenant_001",
            name="Test Tenant",
            contact_email="test@example.com",
        )
        db.add(tenant)

        site = Site(
            tenant_id="test_tenant_001", name="Test Site", location="Test Location"
        )
        db.add(site)
        await db.commit()

        # Create test camera
        camera = Camera(
            tenant_id="test_tenant_001",
            site_id=site.site_id,
            name="Test Camera",
            camera_type="webcam",
            device_index=0,
            is_active=True,
        )
        db.add(camera)
        await db.commit()

        # Test assignment
        result = await assignment_service.assign_camera_with_lease(
            db=db,
            tenant_id="test_tenant_001",
            worker_id="test_worker_001",
            site_id=site.site_id,
        )

        # Should fail - worker not registered
        assert result is None

        print("✅ Lease-based assignment test completed")


@pytest.mark.asyncio
async def test_lease_renewal():
    """Test lease renewal mechanism"""

    async with get_async_session() as db:
        # Create test session
        session = CameraSession(
            camera_id=1,
            tenant_id="test_tenant_001",
            site_id=1,
            worker_id="test_worker_001",
            generation=1,
            state=SessionState.ACTIVE,
            lease_expires_at=datetime.utcnow() + timedelta(seconds=90),
        )
        db.add(session)
        await db.commit()

        # Test renewal
        result = await assignment_service.renew_lease(
            db=db,
            worker_id="test_worker_001",
            renewals=[{"camera_id": 1, "generation": 1}],
        )

        assert len(result["renewals"]) == 1
        assert result["renewals"][0]["status"] == "renewed"

        print("✅ Lease renewal test completed")


@pytest.mark.asyncio
async def test_lease_reclaim():
    """Test expired lease reclamation"""

    async with get_async_session() as db:
        # Create expired session
        expired_session = CameraSession(
            camera_id=2,
            tenant_id="test_tenant_001",
            site_id=1,
            worker_id="test_worker_expired",
            generation=1,
            state=SessionState.ACTIVE,
            lease_expires_at=datetime.utcnow() - timedelta(minutes=2),  # Expired
        )
        db.add(expired_session)
        await db.commit()

        # Test reclaim
        result = await assignment_service.reclaim_expired_leases(db)

        assert result["reclaimed_count"] >= 1

        print("✅ Lease reclaim test completed")


if __name__ == "__main__":
    """Run basic test"""
    asyncio.run(test_lease_based_assignment())
    asyncio.run(test_lease_renewal())
    asyncio.run(test_lease_reclaim())
    print("🎉 All lease delegation tests passed!")
