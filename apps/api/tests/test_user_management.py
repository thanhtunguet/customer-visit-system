import pytest
from app.core.database import get_db
from app.core.security import mint_jwt
from app.main import app
from app.models.database import Base, Tenant, User, UserRole
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="module")
def client():
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def system_admin_user(db_session):
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
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def test_tenant(db_session):
    """Create a test tenant"""
    tenant = Tenant(
        tenant_id="test-tenant",
        name="Test Tenant",
        description="Test tenant for user management tests",
        is_active=True,
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


@pytest.fixture(scope="function")
def admin_headers(system_admin_user):
    """Generate admin auth headers"""
    token = mint_jwt(
        sub=system_admin_user.username, role=system_admin_user.role.value, tenant_id=""
    )
    return {"Authorization": f"Bearer {token}"}


class TestUserAuthentication:
    """Test user authentication endpoints"""

    def test_password_authentication_success(self, client, system_admin_user):
        """Test successful password authentication"""
        response = client.post(
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

    def test_password_authentication_invalid_credentials(
        self, client, system_admin_user
    ):
        """Test authentication with invalid credentials"""
        response = client.post(
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

    def test_password_authentication_inactive_user(self, client, db_session):
        """Test authentication with inactive user"""
        # Create inactive user
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
        db_session.commit()

        response = client.post(
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

    def test_get_current_user(self, client, admin_headers):
        """Test getting current user info"""
        response = client.get("/v1/me", headers=admin_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "testadmin"
        assert data["role"] == "SYSTEM_ADMIN"


class TestUserManagement:
    """Test user management endpoints"""

    def test_list_users_success(self, client, admin_headers, system_admin_user):
        """Test listing users as system admin"""
        response = client.get("/v1/users", headers=admin_headers)

        assert response.status_code == 200
        users = response.json()
        assert len(users) >= 1
        assert any(user["username"] == "testadmin" for user in users)

    def test_list_users_unauthorized(self, client):
        """Test listing users without authentication"""
        response = client.get("/v1/users")
        assert response.status_code == 401

    def test_create_user_success(self, client, admin_headers, test_tenant):
        """Test creating a new user"""
        user_data = {
            "username": "newuser",
            "email": "newuser@test.com",
            "first_name": "New",
            "last_name": "User",
            "password": "newpassword123",
            "role": "TENANT_ADMIN",
            "tenant_id": test_tenant.tenant_id,
            "is_active": True,
        }

        response = client.post("/v1/users", json=user_data, headers=admin_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "newuser"
        assert data["email"] == "newuser@test.com"
        assert data["role"] == "TENANT_ADMIN"
        assert data["tenant_id"] == test_tenant.tenant_id

    def test_create_user_duplicate_username(
        self, client, admin_headers, system_admin_user
    ):
        """Test creating user with duplicate username"""
        user_data = {
            "username": "testadmin",  # Already exists
            "email": "different@test.com",
            "first_name": "Different",
            "last_name": "User",
            "password": "password123",
            "role": "SYSTEM_ADMIN",
        }

        response = client.post("/v1/users", json=user_data, headers=admin_headers)
        assert response.status_code == 400
        assert "Username or email already exists" in response.json()["detail"]

    def test_create_user_validation_errors(self, client, admin_headers):
        """Test user creation validation errors"""
        # Test: non-system admin without tenant_id
        user_data = {
            "username": "invaliduser",
            "email": "invalid@test.com",
            "first_name": "Invalid",
            "last_name": "User",
            "password": "password123",
            "role": "TENANT_ADMIN",
            # Missing tenant_id
        }

        response = client.post("/v1/users", json=user_data, headers=admin_headers)
        assert response.status_code == 400
        assert "tenant_id is required" in response.json()["detail"]

    def test_update_user_success(self, client, admin_headers, test_tenant):
        """Test updating user successfully"""
        # First create a user
        user_data = {
            "username": "updatetest",
            "email": "updatetest@test.com",
            "first_name": "Update",
            "last_name": "Test",
            "password": "password123",
            "role": "SITE_MANAGER",
            "tenant_id": test_tenant.tenant_id,
        }

        create_response = client.post(
            "/v1/users", json=user_data, headers=admin_headers
        )
        assert create_response.status_code == 200
        user_id = create_response.json()["user_id"]

        # Update the user
        update_data = {
            "first_name": "Updated",
            "last_name": "Name",
            "role": "TENANT_ADMIN",
        }

        response = client.put(
            f"/v1/users/{user_id}", json=update_data, headers=admin_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["first_name"] == "Updated"
        assert data["last_name"] == "Name"
        assert data["role"] == "TENANT_ADMIN"

    def test_update_user_not_found(self, client, admin_headers):
        """Test updating non-existent user"""
        response = client.put(
            "/v1/users/nonexistent", json={"first_name": "Test"}, headers=admin_headers
        )
        assert response.status_code == 404

    def test_change_user_password(self, client, admin_headers, test_tenant):
        """Test changing user password"""
        # Create a user first
        user_data = {
            "username": "passwordtest",
            "email": "passwordtest@test.com",
            "first_name": "Password",
            "last_name": "Test",
            "password": "oldpassword",
            "role": "WORKER",
            "tenant_id": test_tenant.tenant_id,
        }

        create_response = client.post(
            "/v1/users", json=user_data, headers=admin_headers
        )
        user_id = create_response.json()["user_id"]

        # Change password
        password_data = {"new_password": "newpassword123"}
        response = client.put(
            f"/v1/users/{user_id}/password", json=password_data, headers=admin_headers
        )

        assert response.status_code == 200
        assert "Password changed successfully" in response.json()["message"]

    def test_toggle_user_status(self, client, admin_headers, test_tenant):
        """Test toggling user active status"""
        # Create a user first
        user_data = {
            "username": "toggletest",
            "email": "toggletest@test.com",
            "first_name": "Toggle",
            "last_name": "Test",
            "password": "password123",
            "role": "WORKER",
            "tenant_id": test_tenant.tenant_id,
            "is_active": True,
        }

        create_response = client.post(
            "/v1/users", json=user_data, headers=admin_headers
        )
        user_id = create_response.json()["user_id"]
        assert create_response.json()["is_active"] is True

        # Toggle status
        response = client.put(
            f"/v1/users/{user_id}/toggle-status", headers=admin_headers
        )

        assert response.status_code == 200
        assert response.json()["is_active"] is False

    def test_delete_user(self, client, admin_headers, test_tenant):
        """Test deleting user"""
        # Create a user first
        user_data = {
            "username": "deletetest",
            "email": "deletetest@test.com",
            "first_name": "Delete",
            "last_name": "Test",
            "password": "password123",
            "role": "WORKER",
            "tenant_id": test_tenant.tenant_id,
        }

        create_response = client.post(
            "/v1/users", json=user_data, headers=admin_headers
        )
        user_id = create_response.json()["user_id"]

        # Delete user
        response = client.delete(f"/v1/users/{user_id}", headers=admin_headers)

        assert response.status_code == 200
        assert "User deleted successfully" in response.json()["message"]

        # Verify user is deleted
        get_response = client.get(f"/v1/users/{user_id}", headers=admin_headers)
        assert get_response.status_code == 404

    def test_cannot_delete_self(self, client, admin_headers, system_admin_user):
        """Test that user cannot delete their own account"""
        response = client.delete(
            f"/v1/users/{system_admin_user.user_id}", headers=admin_headers
        )
        assert response.status_code == 400
        assert "Cannot delete your own account" in response.json()["detail"]


class TestUserRoleBasedAccess:
    """Test role-based access control"""

    def test_non_admin_cannot_access_user_management(
        self, client, db_session, test_tenant
    ):
        """Test that non-system admin users cannot access user management"""
        # Create a tenant admin user
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
        db_session.commit()

        # Get token for tenant admin
        token = mint_jwt(
            sub=tenant_admin.username,
            role=tenant_admin.role.value,
            tenant_id=tenant_admin.tenant_id,
        )
        headers = {"Authorization": f"Bearer {token}"}

        # Try to access user management endpoints
        response = client.get("/v1/users", headers=headers)
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

        # Set password
        user.set_password("testpassword123")

        # Verify password
        assert user.verify_password("testpassword123") is True
        assert user.verify_password("wrongpassword") is False

        # Check that password is hashed
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
        # System admin can access any tenant
        system_admin = User(
            user_id="admin-id",
            username="admin",
            email="admin@test.com",
            first_name="Admin",
            last_name="User",
            role=UserRole.SYSTEM_ADMIN,
        )
        assert system_admin.can_access_tenant("any-tenant") is True

        # Regular user can only access their own tenant
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
