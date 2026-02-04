import hashlib

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.models.database import ApiKey, Tenant


@pytest.mark.asyncio
async def test_health(async_client: AsyncClient):
    r = await async_client.get("/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_token_and_me(async_client: AsyncClient, db_session: AsyncSession):
    tenant = Tenant(tenant_id="t1", name="Test Tenant", is_active=True)
    db_session.add(tenant)
    plain_key = "dev-api-key"
    api_key = ApiKey(
        tenant_id="t1",
        hashed_key=hashlib.sha256(plain_key.encode()).hexdigest(),
        name="Dev Key",
        role="worker",
        is_active=True,
    )
    db_session.add(api_key)
    await db_session.commit()

    r = await async_client.post(
        "/v1/auth/token",
        json={
            "grant_type": "api_key",
            "api_key": "dev-api-key",
            "tenant_id": "t1",
            "role": "worker",
        },
    )
    assert r.status_code == 200
    token = r.json()["access_token"]
    r2 = await async_client.get(
        "/v1/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert r2.status_code == 200
    assert r2.json()["tenant_id"] == "t1"
    assert r2.json()["role"] == "worker"
