from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from common.models import FaceDetectedEvent

from apps.api.app.services.face_service import FaceMatchingService, StaffService


@pytest.fixture
def mock_db_session():
    """Mock database session"""
    return AsyncMock()


@pytest.fixture
def face_event():
    """Sample face detection event"""
    return FaceDetectedEvent(
        tenant_id="t-test",
        site_id="s-test",
        camera_id="c-test",
        timestamp=datetime.now(timezone.utc),
        embedding=[0.1] * 512,
        bbox=[10, 10, 100, 100],
        is_staff_local=False,
    )


@pytest.mark.asyncio
async def test_process_staff_face_event(mock_db_session, face_event):
    """Test processing a face event for staff member"""
    face_event.is_staff_local = True

    service = FaceMatchingService()
    result = await service.process_face_event(
        event=face_event, db_session=mock_db_session, tenant_id="t-test"
    )

    assert result["match"] == "staff"
    assert result["person_id"] is None
    assert result["similarity"] == 1.0
    assert "Staff member identified locally" in result["message"]


@pytest.mark.asyncio
async def test_process_new_customer_face_event(mock_db_session, face_event):
    """Test processing a face event for new customer"""
    service = FaceMatchingService()

    # Mock Milvus to return no matches
    with patch(
        "app.services.face_service.milvus_client.search_similar_faces", return_value=[]
    ):
        with patch("app.services.face_service.milvus_client.insert_embedding"):
            result = await service.process_face_event(
                event=face_event, db_session=mock_db_session, tenant_id="t-test"
            )

    assert result["match"] == "new"
    assert result["person_id"].startswith("c_")
    assert result["person_type"] == "customer"
    assert result["similarity"] == 0.0


@pytest.mark.asyncio
async def test_process_known_customer_face_event(mock_db_session, face_event):
    """Test processing a face event for known customer"""
    service = FaceMatchingService()

    # Mock Milvus to return a match
    mock_matches = [
        {"person_id": "c_existing", "person_type": "customer", "similarity": 0.85}
    ]

    with patch(
        "app.services.face_service.milvus_client.search_similar_faces",
        return_value=mock_matches,
    ):
        with patch("app.services.face_service.milvus_client.insert_embedding"):
            result = await service.process_face_event(
                event=face_event, db_session=mock_db_session, tenant_id="t-test"
            )

    assert result["match"] == "known"
    assert result["person_id"] == "c_existing"
    assert result["person_type"] == "customer"
    assert result["similarity"] == 0.85


@pytest.mark.asyncio
async def test_staff_enrollment(mock_db_session):
    """Test staff member enrollment with face embedding"""
    service = StaffService()
    embedding = [0.1] * 512

    with patch("app.services.face_service.milvus_client.insert_embedding"):
        await service.enroll_staff_member(
            db_session=mock_db_session,
            tenant_id="t-test",
            staff_id="staff-001",
            name="John Doe",
            face_embedding=embedding,
            site_id="s-main",
        )

    # Verify staff object was added to session
    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called_once()
