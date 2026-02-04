import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.core.security import mint_jwt
from apps.api.app.models.database import Tenant, User, UserRole


@pytest.fixture
async def system_admin_user(db_session: AsyncSession):
    """Create a system admin user for testing"""
    user = User(
        user_id="test-admin-id",
        username="testadmin",
        email="admin@test.com",
        first_name="Test",
        last_name="Admin",
        role=UserRole.SYSTEM_ADMIN,
        is_active=True,
    )
    user.set_password("testpassword")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_tenant(db_session: AsyncSession):
    """Create a test tenant"""
    tenant = Tenant(
        tenant_id="test-tenant",
        name="Test Tenant",
        description="Test tenant for user management tests",
        is_active=True,
    )
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)
    return tenant


@pytest.fixture
async def admin_headers(system_admin_user):
    """Generate admin auth headers"""
    token = mint_jwt(
        sub=system_admin_user.username, role=system_admin_user.role.value, tenant_id=""
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
class TestUserAuthentication:
    """Test user authentication endpoints"""

    async def test_password_authentication_success(
        self, async_client: AsyncClient, system_admin_user
    ):
        """Test successful password authentication"""
        response = await async_client.post(
            "/v1/auth/token",
            json={
                "grant_type": "password",
                "username": "testadmin",
                "password": "testpassword",
                "tenant_id": "",
                "role": "system_admin",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_password_authentication_invalid_credentials(
        self, async_client: AsyncClient, system_admin_user
    ):
        """Test authentication with invalid credentials"""
        response = await async_client.post(
            "/v1/auth/token",
            json={
                "grant_type": "password",
                "username": "testadmin",
                "password": "wrongpassword",
                "tenant_id": "",
                "role": "system_admin",
            },
        )

        assert response.status_code == 401
        assert "Invalid username or password" in response.json()["detail"]

    async def test_password_authentication_inactive_user(
        self, async_client: AsyncClient, db_session: AsyncSession
    ):
        """Test authentication with inactive user"""
        user = User(
            user_id="inactive-user",
            username="inactive",
            email="inactive@test.com",
            first_name="Inactive",
            last_name="User",
            role=UserRole.TENANT_ADMIN,
            is_active=False,
        )
        user.set_password("testpassword")
        db_session.add(user)
        await db_session.commit()

        response = await async_client.post(
            "/v1/auth/token",
            json={
                "grant_type": "password",
                "username": "inactive",
                "password": "testpassword",
                "tenant_id": "",
                "role": "tenant_admin",
            },
        )

        assert response.status_code == 401
        assert "Account is disabled" in response.json()["detail"]

    async def test_get_current_user(
        self, async_client: AsyncClient, admin_headers
    ):
        """Test getting current user info"""
        response = await async_client.get("/v1/me", headers=admin_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "testadmin"
        assert data["role"] == "system_admin"


@pytest.mark.asyncio
class TestUserManagement:
    """Test user management endpoints"""

    async def test_list_users_success(
        self, async_client: AsyncClient, admin_headers, system_admin_user
    ):
        """Test listing users as system admin"""
        response = await async_client.get("/v1/users", headers=admin_headers)

        assert response.status_code == 200
        users = response.json()
        assert len(users) >= 1
        assert any(user["username"] == "testadmin" for user in users)

    async def test_list_users_unauthorized(self, async_client: AsyncClient):
        """Test listing users without authentication"""
        response = await async_client.get("/v1/users")
        assert response.status_code == 401

    async def test_create_user_success(
        self, async_client: AsyncClient, admin_headers, test_tenant
    ):
        """Test creating a new user"""
        user_data = {
            "username": "newuser",
            "email": "newuser@test.com",
            "first_name": "New",
            "last_name": "User",
            "password": "newpassword123",
            "role": "tenant_admin",
            "tenant_id": test_tenant.tenant_id,
            "is_active": True,
        }

        response = await async_client.post(
            "/v1/users", json=user_data, headers=admin_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "newuser"
        assert data["email"] == "newuser@test.com"
        assert data["role"] == "tenant_admin"
        assert data["tenant_id"] == test_tenant.tenant_id

    async def test_create_user_duplicate_username(
        self, async_client: AsyncClient, admin_headers, system_admin_user
    ):
        """Test creating user with duplicate username"""
        user_data = {
            "username": "testadmin",
            "email": "different@test.com",
            "first_name": "Different",
            "last_name": "User",
            "password": "password123",
            "role": "system_admin",
        }

        response = await async_client.post(
            "/v1/users", json=user_data, headers=admin_headers
        )
        assert response.status_code == 400
        assert "Username or email already exists" in response.json()["detail"]

    async def test_create_user_validation_errors(
        self, async_client: AsyncClient, admin_headers
    ):
        """Test user creation validation errors"""
        user_data = {
            "username": "invaliduser",
            "email": "invalid@test.com",
            "first_name": "Invalid",
            "last_name": "User",
            "password": "password123",
            "role": "tenant_admin",
        }

        response = await async_client.post(
            "/v1/users", json=user_data, headers=admin_headers
        )
        assert response.status_code == 400
        assert "tenant_id is required" in response.json()["detail"]

    async def test_update_user_success(
        self, async_client: AsyncClient, admin_headers, test_tenant
    ):
        """Test updating user successfully"""
        user_data = {
            "username": "updatetest",
            "email": "updatetest@test.com",
            "first_name": "Update",
            "last_name": "Test",
            "password": "password123",
            "role": "site_manager",
            "tenant_id": test_tenant.tenant_id,
            "site_id": 1,
        }

        create_response = await async_client.post(
            "/v1/users", json=user_data, headers=admin_headers
        )
        assert create_response.status_code == 200
        user_id = create_response.json()["user_id"]

        update_data = {
            "first_name": "Updated",
            "last_name": "Name",
            "role": "tenant_admin",
        }

        response = await async_client.put(
            f"/v1/users/{user_id}", json=update_data, headers=admin_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["first_name"] == "Updated"
        assert data["last_name"] == "Name"
        assert data["role"] == "tenant_admin"

    async def test_update_user_not_found(
        self, async_client: AsyncClient, admin_headers
    ):
        """Test updating non-existent user"""
        response = await async_client.put(
            "/v1/users/nonexistent", json={"first_name": "Test"}, headers=admin_headers
        )
        assert response.status_code == 404

    async def test_change_user_password(
        self, async_client: AsyncClient, admin_headers, test_tenant
    ):
        """Test changing user password"""
        user_data = {
            "username": "passwordtest",
            "email": "passwordtest@test.com",
            "first_name": "Password",
            "last_name": "Test",
            "password": "oldpassword",
            "role": "worker",
            "tenant_id": test_tenant.tenant_id,
        }

        create_response = await async_client.post(
            "/v1/users", json=user_data, headers=admin_headers
        )
        user_id = create_response.json()["user_id"]

        password_data = {"new_password": "newpassword123"}
        response = await async_client.put(
            f"/v1/users/{user_id}/password",
            json=password_data,
            headers=admin_headers,
        )

        assert response.status_code == 200
        assert "Password changed successfully" in response.json()["message"]

    async def test_toggle_user_status(
        self, async_client: AsyncClient, admin_headers, test_tenant
    ):
        """Test toggling user active status"""
        user_data = {
            "username": "toggletest",
            "email": "toggletest@test.com",
            "first_name": "Toggle",
            "last_name": "Test",
            "password": "password123",
            "role": "worker",
            "tenant_id": test_tenant.tenant_id,
            "is_active": True,
        }

        create_response = await async_client.post(
            "/v1/users", json=user_data, headers=admin_headers
        )
        user_id = create_response.json()["user_id"]
        assert create_response.json()["is_active"] is True

        response = await async_client.put(
            f"/v1/users/{user_id}/toggle-status", headers=admin_headers
        )

        assert response.status_code == 200
        assert response.json()["is_active"] is False

    async def test_delete_user(
        self, async_client: AsyncClient, admin_headers, test_tenant
    ):
        """Test deleting user"""
        user_data = {
            "username": "deletetest",
            "email": "deletetest@test.com",
            "first_name": "Delete",
            "last_name": "Test",
            "password": "password123",
            "role": "worker",
            "tenant_id": test_tenant.tenant_id,
        }

        create_response = await async_client.post(
            "/v1/users", json=user_data, headers=admin_headers
        )
        user_id = create_response.json()["user_id"]

        response = await async_client.delete(
            f"/v1/users/{user_id}", headers=admin_headers
        )

        assert response.status_code == 200
        assert "User deleted successfully" in response.json()["message"]

        get_response = await async_client.get(
            f"/v1/users/{user_id}", headers=admin_headers
        )
        assert get_response.status_code == 404

    async def test_cannot_delete_self(
        self, async_client: AsyncClient, admin_headers, system_admin_user
    ):
        """Test that user cannot delete their own account"""
        response = await async_client.delete(
            f"/v1/users/{system_admin_user.user_id}", headers=admin_headers
        )
        assert response.status_code == 400
        assert "Cannot delete your own account" in response.json()["detail"]


@pytest.mark.asyncio
class TestUserRoleBasedAccess:
    """Test role-based access control"""

    async def test_non_admin_cannot_access_user_management(
        self, async_client: AsyncClient, db_session: AsyncSession, test_tenant
    ):
        """Test that non-system admin users cannot access user management"""
        tenant_admin = User(
            user_id="tenant-admin-id",
            username="tenantadmin",
            email="tenantadmin@test.com",
            first_name="Tenant",
            last_name="Admin",
            role=UserRole.TENANT_ADMIN,
            tenant_id=test_tenant.tenant_id,
            is_active=True,
        )
        tenant_admin.set_password("password")
        db_session.add(tenant_admin)
        await db_session.commit()

        token = mint_jwt(
            sub=tenant_admin.username,
            role=tenant_admin.role.value,
            tenant_id=tenant_admin.tenant_id,
        )
        headers = {"Authorization": f"Bearer {token}"}

        response = await async_client.get("/v1/users", headers=headers)
        assert response.status_code == 403
        assert "System administrator access required" in response.json()["detail"]


class TestUserModel:
    """Test User model functionality"""

    def test_password_hashing(self):
        """Test password hashing and verification"""
        user = User(
            user_id="test-id",
            username="testuser",
            email="test@test.com",
            first_name="Test",
            last_name="User",
            role=UserRole.WORKER,
        )

        user.set_password("testpassword123")

        assert user.verify_password("testpassword123") is True
        assert user.verify_password("wrongpassword") is False

        assert user.password_hash != "testpassword123"
        assert user.password_hash.startswith("$2b$")

    def test_full_name_property(self):
        """Test full name property"""
        user = User(
            user_id="test-id",
            username="testuser",
            email="test@test.com",
            first_name="John",
            last_name="Doe",
            role=UserRole.WORKER,
        )

        assert user.full_name == "John Doe"

    def test_can_access_tenant(self):
        """Test tenant access control"""
        system_admin = User(
            user_id="admin-id",
            username="admin",
            email="admin@test.com",
            first_name="Admin",
            last_name="User",
            role=UserRole.SYSTEM_ADMIN,
        )
        assert system_admin.can_access_tenant("any-tenant") is True

        tenant_user = User(
            user_id="user-id",
            username="user",
            email="user@test.com",
            first_name="Regular",
            last_name="User",
            role=UserRole.TENANT_ADMIN,
            tenant_id="user-tenant",
        )
        assert tenant_user.can_access_tenant("user-tenant") is True
        assert tenant_user.can_access_tenant("other-tenant") is False
