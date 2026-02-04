import json
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from apps.api.app.core.security import mint_jwt
from apps.api.app.services.face_service import face_service


@pytest.mark.asyncio
async def test_ingest_face(async_client: AsyncClient):
    tok = mint_jwt(sub="worker", role="worker", tenant_id="t1")
    evt = {
        "tenant_id": "t1",
        "site_id": 1,
        "camera_id": 1,
        "timestamp": "2024-01-01T00:00:00Z",
        "embedding": [0.0] * 512,
        "bbox": [0, 0, 10, 10],
        "confidence": 0.9,
        "is_staff_local": False,
    }

    mock_result = {
        "match": "unknown",
        "person_id": None,
        "similarity": 0.0,
        "visit_id": None,
        "person_type": "customer",
    }

    with patch.object(
        face_service, "process_face_event_with_image", return_value=mock_result
    ):
        r = await async_client.post(
            "/v1/events/face",
            data={"event_data": json.dumps(evt)},
            files={"face_image": ("face.jpg", b"fake", "image/jpeg")},
            headers={"Authorization": f"Bearer {tok}"},
        )

    assert r.status_code == 200
    body = r.json()
    assert body["match"] == "unknown"
