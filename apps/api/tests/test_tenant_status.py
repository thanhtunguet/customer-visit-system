import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Tenant
from app.core.security import create_access_token


@pytest.mark.asyncio
async def test_toggle_tenant_status_activate(async_client: AsyncClient, db_session: AsyncSession):
    """Test activating an inactive tenant"""
    # Create a test tenant (inactive)
    test_tenant = Tenant(
        tenant_id="test-tenant-inactive",
        name="Test Inactive Tenant",
        description="Test tenant for status toggle",
        is_active=False
    )
    db_session.add(test_tenant)
    await db_session.commit()
    
    # Create system admin token
    token = create_access_token(
        data={"sub": "admin", "role": "system_admin", "tenant_id": "system"}
    )
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Toggle status to active
    response = await async_client.patch(
        f"/v1/tenants/test-tenant-inactive/status",
        json={"is_active": True},
        headers=headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["tenant_id"] == "test-tenant-inactive"
    assert data["is_active"] is True
    assert data["name"] == "Test Inactive Tenant"
    assert data["description"] == "Test tenant for status toggle"


@pytest.mark.asyncio
async def test_toggle_tenant_status_deactivate(async_client: AsyncClient, db_session: AsyncSession):
    """Test deactivating an active tenant"""
    # Create a test tenant (active)
    test_tenant = Tenant(
        tenant_id="test-tenant-active",
        name="Test Active Tenant",
        description="Test tenant for status toggle",
        is_active=True
    )
    db_session.add(test_tenant)
    await db_session.commit()
    
    # Create system admin token
    token = create_access_token(
        data={"sub": "admin", "role": "system_admin", "tenant_id": "system"}
    )
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Toggle status to inactive
    response = await async_client.patch(
        f"/v1/tenants/test-tenant-active/status",
        json={"is_active": False},
        headers=headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["tenant_id"] == "test-tenant-active"
    assert data["is_active"] is False
    assert data["name"] == "Test Active Tenant"


@pytest.mark.asyncio
async def test_toggle_tenant_status_forbidden_tenant_admin(async_client: AsyncClient, db_session: AsyncSession):
    """Test that tenant admin cannot toggle tenant status"""
    # Create a test tenant
    test_tenant = Tenant(
        tenant_id="test-tenant-forbidden",
        name="Test Tenant",
        is_active=True
    )
    db_session.add(test_tenant)
    await db_session.commit()
    
    # Create tenant admin token (not system admin)
    token = create_access_token(
        data={"sub": "tenant_admin", "role": "tenant_admin", "tenant_id": "test-tenant-forbidden"}
    )
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Try to toggle status (should fail)
    response = await async_client.patch(
        f"/v1/tenants/test-tenant-forbidden/status",
        json={"is_active": False},
        headers=headers
    )
    
    assert response.status_code == 403
    data = response.json()
    assert "Only system administrators can modify tenant status" in data["detail"]


@pytest.mark.asyncio
async def test_toggle_tenant_status_not_found(async_client: AsyncClient):
    """Test toggling status for non-existent tenant"""
    # Create system admin token
    token = create_access_token(
        data={"sub": "admin", "role": "system_admin", "tenant_id": "system"}
    )
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Try to toggle status for non-existent tenant
    response = await async_client.patch(
        f"/v1/tenants/non-existent-tenant/status",
        json={"is_active": True},
        headers=headers
    )
    
    assert response.status_code == 404
    data = response.json()
    assert "Tenant not found" in data["detail"]


@pytest.mark.asyncio
async def test_create_tenant_with_description(async_client: AsyncClient):
    """Test creating a tenant with description"""
    # Create system admin token
    token = create_access_token(
        data={"sub": "admin", "role": "system_admin", "tenant_id": "system"}
    )
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Create tenant with description
    tenant_data = {
        "tenant_id": "new-tenant-with-desc",
        "name": "New Tenant with Description",
        "description": "This is a test tenant with a description"
    }
    
    response = await async_client.post(
        "/v1/tenants",
        json=tenant_data,
        headers=headers
    )
    
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
        is_active=True
    )
    db_session.add(test_tenant)
    await db_session.commit()
    
    # Create system admin token
    token = create_access_token(
        data={"sub": "admin", "role": "system_admin", "tenant_id": "system"}
    )
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Update tenant
    update_data = {
        "name": "Updated Name",
        "description": "Updated description"
    }
    
    response = await async_client.put(
        f"/v1/tenants/test-tenant-update",
        json=update_data,
        headers=headers
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
        is_active=False
    )
    db_session.add(test_tenant)
    await db_session.commit()
    
    # Create system admin token
    token = create_access_token(
        data={"sub": "admin", "role": "system_admin", "tenant_id": "system"}
    )
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Get tenant
    response = await async_client.get(
        f"/v1/tenants/test-tenant-get",
        headers=headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["tenant_id"] == "test-tenant-get"
    assert data["name"] == "Test Get Tenant"
    assert data["description"] == "Test tenant for GET endpoint"
    assert data["is_active"] is False


@pytest.mark.asyncio
async def test_delete_tenant(async_client: AsyncClient, db_session: AsyncSession):
    """Test deleting a tenant"""
    # Create a test tenant
    test_tenant = Tenant(
        tenant_id="test-tenant-delete",
        name="Test Delete Tenant",
        is_active=True
    )
    db_session.add(test_tenant)
    await db_session.commit()
    
    # Create system admin token
    token = create_access_token(
        data={"sub": "admin", "role": "system_admin", "tenant_id": "system"}
    )
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Delete tenant
    response = await async_client.delete(
        f"/v1/tenants/test-tenant-delete",
        headers=headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "deleted successfully" in data["message"]
    
    # Verify tenant is deleted
    get_response = await async_client.get(
        f"/v1/tenants/test-tenant-delete",
        headers=headers
    )
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_create_duplicate_tenant_fails(async_client: AsyncClient, db_session: AsyncSession):
    """Test that creating a tenant with duplicate ID fails"""
    # Create a test tenant
    test_tenant = Tenant(
        tenant_id="duplicate-tenant",
        name="Original Tenant",
        is_active=True
    )
    db_session.add(test_tenant)
    await db_session.commit()
    
    # Create system admin token
    token = create_access_token(
        data={"sub": "admin", "role": "system_admin", "tenant_id": "system"}
    )
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Try to create duplicate tenant
    tenant_data = {
        "tenant_id": "duplicate-tenant",
        "name": "Duplicate Tenant",
    }
    
    response = await async_client.post(
        "/v1/tenants",
        json=tenant_data,
        headers=headers
    )
    
    assert response.status_code == 409
    data = response.json()
    assert "already exists" in data["detail"]