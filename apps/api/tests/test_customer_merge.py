import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_merge_noop_same_customer(admin_token, async_client: AsyncClient):
    payload = {
        "primary_customer_id": 123,
        "secondary_customer_id": 123,
        "notes": "duplicate record",
    }
    headers = {"Authorization": f"Bearer {admin_token}"}
    r = await async_client.post("/v1/customers/merge", json=payload, headers=headers)
    assert r.status_code == 200 or r.status_code == 202
    data = r.json()
    assert data.get("status") in ("accepted", None)
