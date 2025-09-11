import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.core.security import mint_jwt
from apps.api.app.models.database import (ApiKey, Camera, Customer, Site,
                                          Staff, StaffFaceImage, Tenant, Visit)


@pytest.mark.asyncio
async def test_toggle_tenant_status_activate(
    async_client: AsyncClient, db_session: AsyncSession
):
    """Test activating an inactive tenant"""
    # Create a test tenant (inactive)
    test_tenant = Tenant(
        tenant_id="test-tenant-inactive",
        name="Test Inactive Tenant",
        description="Test tenant for status toggle",
        is_active=False,
    )
    db_session.add(test_tenant)
    await db_session.commit()

    # Create system admin token
    token = mint_jwt(sub="admin", role="system_admin", tenant_id="system")

    headers = {"Authorization": f"Bearer {token}"}

    # Toggle status to active
    response = await async_client.patch(
        "/v1/tenants/test-tenant-inactive/status",
        json={"is_active": True},
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tenant_id"] == "test-tenant-inactive"
    assert data["is_active"] is True
    assert data["name"] == "Test Inactive Tenant"
    assert data["description"] == "Test tenant for status toggle"


@pytest.mark.asyncio
async def test_toggle_tenant_status_deactivate(
    async_client: AsyncClient, db_session: AsyncSession
):
    """Test deactivating an active tenant"""
    # Create a test tenant (active)
    test_tenant = Tenant(
        tenant_id="test-tenant-active",
        name="Test Active Tenant",
        description="Test tenant for status toggle",
        is_active=True,
    )
    db_session.add(test_tenant)
    await db_session.commit()

    # Create system admin token
    token = mint_jwt(sub="admin", role="system_admin", tenant_id="system")

    headers = {"Authorization": f"Bearer {token}"}

    # Toggle status to inactive
    response = await async_client.patch(
        "/v1/tenants/test-tenant-active/status",
        json={"is_active": False},
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tenant_id"] == "test-tenant-active"
    assert data["is_active"] is False
    assert data["name"] == "Test Active Tenant"


@pytest.mark.asyncio
async def test_toggle_tenant_status_forbidden_tenant_admin(
    async_client: AsyncClient, db_session: AsyncSession
):
    """Test that tenant admin cannot toggle tenant status"""
    # Create a test tenant
    test_tenant = Tenant(
        tenant_id="test-tenant-forbidden", name="Test Tenant", is_active=True
    )
    db_session.add(test_tenant)
    await db_session.commit()

    # Create tenant admin token (not system admin)
    token = mint_jwt(
        data={
            "sub": "tenant_admin",
            "role": "tenant_admin",
            "tenant_id": "test-tenant-forbidden",
        }
    )

    headers = {"Authorization": f"Bearer {token}"}

    # Try to toggle status (should fail)
    response = await async_client.patch(
        "/v1/tenants/test-tenant-forbidden/status",
        json={"is_active": False},
        headers=headers,
    )

    assert response.status_code == 403
    data = response.json()
    assert "Only system administrators can modify tenant status" in data["detail"]


@pytest.mark.asyncio
async def test_toggle_tenant_status_not_found(async_client: AsyncClient):
    """Test toggling status for non-existent tenant"""
    # Create system admin token
    token = mint_jwt(sub="admin", role="system_admin", tenant_id="system")

    headers = {"Authorization": f"Bearer {token}"}

    # Try to toggle status for non-existent tenant
    response = await async_client.patch(
        "/v1/tenants/non-existent-tenant/status",
        json={"is_active": True},
        headers=headers,
    )

    assert response.status_code == 404
    data = response.json()
    assert "Tenant not found" in data["detail"]


@pytest.mark.asyncio
async def test_create_tenant_with_description(async_client: AsyncClient):
    """Test creating a tenant with description"""
    # Create system admin token
    token = mint_jwt(sub="admin", role="system_admin", tenant_id="system")

    headers = {"Authorization": f"Bearer {token}"}

    # Create tenant with description
    tenant_data = {
        "tenant_id": "new-tenant-with-desc",
        "name": "New Tenant with Description",
        "description": "This is a test tenant with a description",
    }

    response = await async_client.post("/v1/tenants", json=tenant_data, headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["tenant_id"] == "new-tenant-with-desc"
    assert data["name"] == "New Tenant with Description"
    assert data["description"] == "This is a test tenant with a description"
    assert data["is_active"] is True  # Should default to True


@pytest.mark.asyncio
async def test_update_tenant(async_client: AsyncClient, db_session: AsyncSession):
    """Test updating tenant information"""
    # Create a test tenant
    test_tenant = Tenant(
        tenant_id="test-tenant-update",
        name="Original Name",
        description="Original description",
        is_active=True,
    )
    db_session.add(test_tenant)
    await db_session.commit()

    # Create system admin token
    token = mint_jwt(sub="admin", role="system_admin", tenant_id="system")

    headers = {"Authorization": f"Bearer {token}"}

    # Update tenant
    update_data = {"name": "Updated Name", "description": "Updated description"}

    response = await async_client.put(
        "/v1/tenants/test-tenant-update", json=update_data, headers=headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tenant_id"] == "test-tenant-update"
    assert data["name"] == "Updated Name"
    assert data["description"] == "Updated description"
    assert data["is_active"] is True  # Should remain unchanged


@pytest.mark.asyncio
async def test_get_single_tenant(async_client: AsyncClient, db_session: AsyncSession):
    """Test getting a single tenant by ID"""
    # Create a test tenant
    test_tenant = Tenant(
        tenant_id="test-tenant-get",
        name="Test Get Tenant",
        description="Test tenant for GET endpoint",
        is_active=False,
    )
    db_session.add(test_tenant)
    await db_session.commit()

    # Create system admin token
    token = mint_jwt(sub="admin", role="system_admin", tenant_id="system")

    headers = {"Authorization": f"Bearer {token}"}

    # Get tenant
    response = await async_client.get("/v1/tenants/test-tenant-get", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["tenant_id"] == "test-tenant-get"
    assert data["name"] == "Test Get Tenant"
    assert data["description"] == "Test tenant for GET endpoint"
    assert data["is_active"] is False


async def test_delete_tenant(async_client: AsyncClient, db_session: AsyncSession):
    """Test deleting an empty tenant (updated to work with validation)"""
    # Create a test tenant
    test_tenant = Tenant(
        tenant_id="test-tenant-delete", name="Test Delete Tenant", is_active=True
    )
    db_session.add(test_tenant)
    await db_session.commit()

    # Create system admin token
    token = mint_jwt(sub="admin", role="system_admin", tenant_id="system")

    headers = {"Authorization": f"Bearer {token}"}

    # Delete tenant (should succeed as it's empty)
    response = await async_client.delete(
        "/v1/tenants/test-tenant-delete", headers=headers
    )

    assert response.status_code == 200
    data = response.json()
    assert "deleted successfully" in data["message"]

    # Verify tenant is deleted
    get_response = await async_client.get(
        "/v1/tenants/test-tenant-delete", headers=headers
    )
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_create_duplicate_tenant_fails(
    async_client: AsyncClient, db_session: AsyncSession
):
    """Test that creating a tenant with duplicate ID fails"""
    # Create a test tenant
    test_tenant = Tenant(
        tenant_id="duplicate-tenant", name="Original Tenant", is_active=True
    )
    db_session.add(test_tenant)
    await db_session.commit()

    # Create system admin token
    token = mint_jwt(sub="admin", role="system_admin", tenant_id="system")

    headers = {"Authorization": f"Bearer {token}"}

    # Try to create duplicate tenant
    tenant_data = {
        "tenant_id": "duplicate-tenant",
        "name": "Duplicate Tenant",
    }

    response = await async_client.post("/v1/tenants", json=tenant_data, headers=headers)

    assert response.status_code == 409
    data = response.json()
    assert "already exists" in data["detail"]


@pytest.mark.asyncio
async def test_delete_tenant_with_sites_having_cameras_fails(
    async_client: AsyncClient, db_session: AsyncSession
):
    """Test that deleting a tenant with sites containing cameras fails"""
    # Create a test tenant
    test_tenant = Tenant(
        tenant_id="test-tenant-with-cameras",
        name="Test Tenant with Cameras",
        is_active=True,
    )
    db_session.add(test_tenant)
    await db_session.flush()

    # Create a site for the tenant
    test_site = Site(
        tenant_id="test-tenant-with-cameras", name="Test Site", location="Test Location"
    )
    db_session.add(test_site)
    await db_session.flush()

    # Create a camera for the site
    test_camera = Camera(
        site_id=test_site.site_id,
        name="Test Camera",
        rtsp_url="rtsp://test.url",
        is_active=True,
    )
    db_session.add(test_camera)
    await db_session.commit()

    # Create system admin token
    token = mint_jwt(sub="admin", role="system_admin", tenant_id="system")

    headers = {"Authorization": f"Bearer {token}"}

    # Try to delete tenant (should fail due to cameras)
    response = await async_client.delete(
        "/v1/tenants/test-tenant-with-cameras", headers=headers
    )

    assert response.status_code == 400
    data = response.json()
    assert "Cannot delete tenant" in data["detail"]
    assert "camera(s)" in data["detail"]


@pytest.mark.asyncio
async def test_delete_tenant_with_staff_fails(
    async_client: AsyncClient, db_session: AsyncSession
):
    """Test that deleting a tenant with staff fails"""
    # Create a test tenant
    test_tenant = Tenant(
        tenant_id="test-tenant-with-staff",
        name="Test Tenant with Staff",
        is_active=True,
    )
    db_session.add(test_tenant)
    await db_session.flush()

    # Create staff for the tenant
    test_staff = Staff(
        tenant_id="test-tenant-with-staff", name="Test Staff", site_id=1, is_active=True
    )
    db_session.add(test_staff)
    await db_session.commit()

    # Create system admin token
    token = mint_jwt(sub="admin", role="system_admin", tenant_id="system")

    headers = {"Authorization": f"Bearer {token}"}

    # Try to delete tenant (should fail due to staff)
    response = await async_client.delete(
        "/v1/tenants/test-tenant-with-staff", headers=headers
    )

    assert response.status_code == 400
    data = response.json()
    assert "Cannot delete tenant" in data["detail"]
    assert "staff member(s)" in data["detail"]


@pytest.mark.asyncio
async def test_delete_tenant_with_customers_fails(
    async_client: AsyncClient, db_session: AsyncSession
):
    """Test that deleting a tenant with customers fails"""
    # Create a test tenant
    test_tenant = Tenant(
        tenant_id="test-tenant-with-customers",
        name="Test Tenant with Customers",
        is_active=True,
    )
    db_session.add(test_tenant)
    await db_session.flush()

    # Create customer for the tenant
    test_customer = Customer(
        tenant_id="test-tenant-with-customers",
        name="Test Customer",
        gender="unknown",
        visit_count=1,
    )
    db_session.add(test_customer)
    await db_session.commit()

    # Create system admin token
    token = mint_jwt(sub="admin", role="system_admin", tenant_id="system")

    headers = {"Authorization": f"Bearer {token}"}

    # Try to delete tenant (should fail due to customers)
    response = await async_client.delete(
        "/v1/tenants/test-tenant-with-customers", headers=headers
    )

    assert response.status_code == 400
    data = response.json()
    assert "Cannot delete tenant" in data["detail"]
    assert "customer(s)" in data["detail"]


@pytest.mark.asyncio
async def test_delete_tenant_with_api_keys_fails(
    async_client: AsyncClient, db_session: AsyncSession
):
    """Test that deleting a tenant with API keys fails"""
    # Create a test tenant
    test_tenant = Tenant(
        tenant_id="test-tenant-with-api-keys",
        name="Test Tenant with API Keys",
        is_active=True,
    )
    db_session.add(test_tenant)
    await db_session.flush()

    # Create API key for the tenant
    test_api_key = ApiKey(
        tenant_id="test-tenant-with-api-keys",
        key_name="Test API Key",
        key_hash="test_hash",
        is_active=True,
    )
    db_session.add(test_api_key)
    await db_session.commit()

    # Create system admin token
    token = mint_jwt(sub="admin", role="system_admin", tenant_id="system")

    headers = {"Authorization": f"Bearer {token}"}

    # Try to delete tenant (should fail due to API keys)
    response = await async_client.delete(
        "/v1/tenants/test-tenant-with-api-keys", headers=headers
    )

    assert response.status_code == 400
    data = response.json()
    assert "Cannot delete tenant" in data["detail"]
    assert "API key(s)" in data["detail"]


@pytest.mark.asyncio
async def test_delete_tenant_with_visits_fails(
    async_client: AsyncClient, db_session: AsyncSession
):
    """Test that deleting a tenant with visit records fails"""
    # Create a test tenant
    test_tenant = Tenant(
        tenant_id="test-tenant-with-visits",
        name="Test Tenant with Visits",
        is_active=True,
    )
    db_session.add(test_tenant)
    await db_session.flush()

    # Create visit record for the tenant
    test_visit = Visit(
        tenant_id="test-tenant-with-visits",
        visit_id="test-visit-1",
        person_id=1,
        person_type="customer",
        site_id=1,
        camera_id=1,
        confidence_score=0.95,
    )
    db_session.add(test_visit)
    await db_session.commit()

    # Create system admin token
    token = mint_jwt(sub="admin", role="system_admin", tenant_id="system")

    headers = {"Authorization": f"Bearer {token}"}

    # Try to delete tenant (should fail due to visits)
    response = await async_client.delete(
        "/v1/tenants/test-tenant-with-visits", headers=headers
    )

    assert response.status_code == 400
    data = response.json()
    assert "Cannot delete tenant" in data["detail"]
    assert "visit record(s)" in data["detail"]


@pytest.mark.asyncio
async def test_delete_tenant_with_staff_face_images_fails(
    async_client: AsyncClient, db_session: AsyncSession
):
    """Test that deleting a tenant with staff face images fails"""
    # Create a test tenant
    test_tenant = Tenant(
        tenant_id="test-tenant-with-face-images",
        name="Test Tenant with Face Images",
        is_active=True,
    )
    db_session.add(test_tenant)
    await db_session.flush()

    # Create staff face image for the tenant
    test_face_image = StaffFaceImage(
        tenant_id="test-tenant-with-face-images",
        image_id="test-image-1",
        staff_id=1,
        image_path="/path/to/face/image.jpg",
        is_primary=True,
    )
    db_session.add(test_face_image)
    await db_session.commit()

    # Create system admin token
    token = mint_jwt(sub="admin", role="system_admin", tenant_id="system")

    headers = {"Authorization": f"Bearer {token}"}

    # Try to delete tenant (should fail due to face images)
    response = await async_client.delete(
        "/v1/tenants/test-tenant-with-face-images", headers=headers
    )

    assert response.status_code == 400
    data = response.json()
    assert "Cannot delete tenant" in data["detail"]
    assert "staff face image(s)" in data["detail"]


@pytest.mark.asyncio
async def test_delete_empty_tenant_with_empty_sites_succeeds(
    async_client: AsyncClient, db_session: AsyncSession
):
    """Test that deleting a tenant with only empty sites (no cameras) succeeds"""
    # Create a test tenant
    test_tenant = Tenant(
        tenant_id="test-tenant-empty-sites",
        name="Test Tenant with Empty Sites",
        is_active=True,
    )
    db_session.add(test_tenant)
    await db_session.flush()

    # Create empty sites for the tenant (no cameras)
    test_site1 = Site(
        tenant_id="test-tenant-empty-sites", name="Empty Site 1", location="Location 1"
    )
    test_site2 = Site(
        tenant_id="test-tenant-empty-sites", name="Empty Site 2", location="Location 2"
    )
    db_session.add_all([test_site1, test_site2])
    await db_session.commit()

    # Create system admin token
    token = mint_jwt(sub="admin", role="system_admin", tenant_id="system")

    headers = {"Authorization": f"Bearer {token}"}

    # Delete tenant (should succeed as sites are empty)
    response = await async_client.delete(
        "/v1/tenants/test-tenant-empty-sites", headers=headers
    )

    assert response.status_code == 200
    data = response.json()
    assert "deleted successfully" in data["message"]

    # Verify tenant is deleted
    get_response = await async_client.get(
        "/v1/tenants/test-tenant-empty-sites", headers=headers
    )
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_completely_empty_tenant_succeeds(
    async_client: AsyncClient, db_session: AsyncSession
):
    """Test that deleting a completely empty tenant (no sites, staff, customers, API keys) succeeds"""
    # Create a test tenant with no dependencies
    test_tenant = Tenant(
        tenant_id="test-tenant-completely-empty",
        name="Test Empty Tenant",
        is_active=True,
    )
    db_session.add(test_tenant)
    await db_session.commit()

    # Create system admin token
    token = mint_jwt(sub="admin", role="system_admin", tenant_id="system")

    headers = {"Authorization": f"Bearer {token}"}

    # Delete tenant (should succeed)
    response = await async_client.delete(
        "/v1/tenants/test-tenant-completely-empty", headers=headers
    )

    assert response.status_code == 200
    data = response.json()
    assert "deleted successfully" in data["message"]
