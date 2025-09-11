from unittest.mock import AsyncMock, patch

import pytest
from common.models import FaceDetectedEvent

from apps.api.app.services.face_service import face_service


@pytest.mark.asyncio
async def test_low_quality_rejected(monkeypatch):
    # Set strict quality
    face_service.min_confidence_score = 0.7
    evt = FaceDetectedEvent(
        tenant_id="t1",
        site_id=1,
        camera_id=1,
        timestamp=__import__("datetime").datetime.utcnow(),
        embedding=[0.0] * 512,
        bbox=[0, 0, 10, 10],
        confidence=0.5,
        snapshot_url=None,
        is_staff_local=False,
    )

    with patch(
        "apps.api.app.services.face_service.milvus_client.search_similar_faces",
        new=AsyncMock(return_value=[]),
    ):
        db_session = AsyncMock()
        res = await face_service.process_face_event(evt, db_session, tenant_id="t1")
        assert res["match"] == "rejected"


@pytest.mark.asyncio
async def test_prefers_known_with_soft_threshold_and_margin(monkeypatch):
    # Tune thresholds
    face_service.embedding_distance_thr = 0.85
    face_service.merge_distance_thr = 0.90
    face_service.merge_margin = 0.03
    face_service.min_confidence_score = 0.2

    evt = FaceDetectedEvent(
        tenant_id="t1",
        site_id=1,
        camera_id=1,
        timestamp=__import__("datetime").datetime.utcnow(),
        embedding=[0.01] * 512,
        bbox=[0, 0, 10, 10],
        confidence=0.99,
        snapshot_url=None,
        is_staff_local=False,
    )

    # Return two candidates: best 0.88, second 0.80; margin=0.08 >= 0.03
    matches = [
        {"person_id": 42, "person_type": "customer", "similarity": 0.88},
        {"person_id": 43, "person_type": "customer", "similarity": 0.80},
    ]
    with patch(
        "apps.api.app.services.face_service.milvus_client.search_similar_faces",
        new=AsyncMock(return_value=matches),
    ):
        with patch(
            "apps.api.app.services.face_service.milvus_client.insert_embedding",
            new=AsyncMock(return_value="ok"),
        ):
            db_session = AsyncMock()
            res = await face_service.process_face_event(evt, db_session, tenant_id="t1")
            assert res["match"] == "known"
            assert res["person_id"] == 42
