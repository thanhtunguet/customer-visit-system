from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import Optional

import httpx
from pydantic import BaseModel


API_URL = os.getenv("API_URL", "http://api:8080")
TENANT_ID = os.getenv("TENANT_ID", "t-dev")
SITE_ID = os.getenv("SITE_ID", "s-1")
CAMERA_ID = os.getenv("CAMERA_ID", "c-1")
WORKER_API_KEY = os.getenv("WORKER_API_KEY", "dev-api-key")


class FaceDetectedEvent(BaseModel):
    tenant_id: str
    site_id: str
    camera_id: str
    timestamp: datetime
    embedding: list[float]
    bbox: list[float]
    snapshot_url: Optional[str] = None
    is_staff_local: bool = False


async def get_token(client: httpx.AsyncClient) -> str:
    r = await client.post(
        f"{API_URL}/v1/auth/token",
        json={
            "grant_type": "api_key",
            "api_key": WORKER_API_KEY,
            "tenant_id": TENANT_ID,
            "role": "worker",
        },
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["access_token"]


async def simulate_event_post(token: str, client: httpx.AsyncClient) -> None:
    evt = FaceDetectedEvent(
        tenant_id=TENANT_ID,
        site_id=SITE_ID,
        camera_id=CAMERA_ID,
        timestamp=datetime.now(timezone.utc),
        embedding=[0.0] * 512,
        bbox=[10, 10, 100, 100],
        snapshot_url=None,
    )
    r = await client.post(
        f"{API_URL}/v1/events/face",
        json=evt.model_dump(mode="json"),
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    # Endpoint may not exist yet in bootstrap; ignore failures
    print("POST /v1/events/face =>", r.status_code)


async def main():
    async with httpx.AsyncClient() as client:
        token = await get_token(client)
        await simulate_event_post(token, client)


if __name__ == "__main__":
    asyncio.run(main())

