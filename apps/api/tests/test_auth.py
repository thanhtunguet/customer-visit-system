import hashlib

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.core.security import mint_jwt, verify_jwt
from apps.api.app.models.database import ApiKey, Tenant, User, UserRole


def test_jwt_minting_and_verification():
    """Test JWT token creation and verification"""
    token = mint_jwt(
        sub="test-user", role="tenant_admin", tenant_id="t-test", ttl_sec=3600
    )

    assert isinstance(token, str)
    assert len(token) > 0

    # Verify token
    payload = verify_jwt(token)
    assert payload["sub"] == "test-user"
    assert payload["role"] == "tenant_admin"
    assert payload["tenant_id"] == "t-test"


@pytest.mark.asyncio
async def test_api_key_authentication(
    async_client: AsyncClient, db_session: AsyncSession
):
    """Test API key authentication flow"""
    tenant = Tenant(tenant_id="t-test", name="Test Tenant", is_active=True)
    db_session.add(tenant)
    await db_session.commit()

    plain_key = "dev-api-key"
    api_key = ApiKey(
        tenant_id="t-test",
        hashed_key=hashlib.sha256(plain_key.encode()).hexdigest(),
        name="Dev Key",
        role="worker",
        is_active=True,
    )
    db_session.add(api_key)
    await db_session.commit()

    response = await async_client.post(
        "/v1/auth/token",
        json={
            "grant_type": "api_key",
            "api_key": plain_key,
            "tenant_id": "t-test",
            "role": "worker",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_invalid_api_key(async_client: AsyncClient):
    """Test invalid API key returns 401"""
    response = await async_client.post(
        "/v1/auth/token",
        json={
            "grant_type": "api_key",
            "api_key": "invalid-key",
            "tenant_id": "t-test",
            "role": "worker",
        },
    )

    assert response.status_code == 401
    assert "Invalid API key" in response.json()["detail"]


@pytest.mark.asyncio
async def test_password_authentication(
    async_client: AsyncClient, db_session: AsyncSession
):
    """Test password-based authentication (dev mode)"""
    tenant = Tenant(tenant_id="t-test", name="Test Tenant", is_active=True)
    db_session.add(tenant)
    user = User(
        username="admin",
        email="admin@test.com",
        first_name="Admin",
        last_name="User",
        role=UserRole.TENANT_ADMIN,
        tenant_id="t-test",
        is_active=True,
    )
    user.set_password("password")
    db_session.add(user)
    await db_session.commit()

    response = await async_client.post(
        "/v1/auth/token",
        json={
            "grant_type": "password",
            "username": "admin",
            "password": "password",
            "tenant_id": "t-test",
            "role": "tenant_admin",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data


@pytest.mark.asyncio
async def test_protected_endpoint_without_token(async_client: AsyncClient):
    """Test protected endpoint returns 401 without token"""
    response = await async_client.get("/v1/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_protected_endpoint_with_token(
    async_client: AsyncClient, db_session: AsyncSession
):
    """Test protected endpoint works with valid token"""
    tenant = Tenant(tenant_id="t-test", name="Test Tenant", is_active=True)
    db_session.add(tenant)
    plain_key = "dev-api-key"
    api_key = ApiKey(
        tenant_id="t-test",
        hashed_key=hashlib.sha256(plain_key.encode()).hexdigest(),
        name="Dev Key",
        role="worker",
        is_active=True,
    )
    db_session.add(api_key)
    await db_session.commit()

    # Get token
    token_response = await async_client.post(
        "/v1/auth/token",
        json={
            "grant_type": "api_key",
            "api_key": plain_key,
            "tenant_id": "t-test",
            "role": "worker",
        },
    )
    token = token_response.json()["access_token"]

    # Use token
    response = await async_client.get(
        "/v1/me", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tenant_id"] == "t-test"
    assert data["role"] == "worker"
