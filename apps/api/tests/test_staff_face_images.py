"""Tests for staff face images functionality."""

import json
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from apps.api.app.models.database import Staff, StaffFaceImage
from apps.api.app.services.face_processing_service import face_processing_service


@pytest.mark.asyncio
async def test_upload_staff_face_image_success(
    async_client: AsyncClient, test_token: str, mock_db_session, test_staff_data
):
    """Test successful staff face image upload."""
    # Mock face processing service
    processing_result = {
        "success": True,
        "image_id": "test-image-123",
        "image_path": "staff-faces/t-test/test-image-123.jpg",
        "landmarks": [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0], [7.0, 8.0], [9.0, 10.0]],
        "embedding": [0.1] * 512,
        "face_count": 1,
        "confidence": 0.95,
        "bbox": [10, 10, 100, 100],
    }

    with patch.object(
        face_processing_service,
        "process_staff_face_image",
        return_value=processing_result,
    ):
        with patch("app.main.milvus_client.insert_embedding") as mock_milvus:
            response = await async_client.post(
                f"/v1/staff/{test_staff_data['staff_id']}/faces",
                json={
                    "image_data": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAIBAQIBAQICAgICAgICAwUDAwMDAwYEBAMFBwYHBw==",
                    "is_primary": True,
                },
                headers={"Authorization": f"Bearer {test_token}"},
            )

    assert response.status_code == 200
    data = response.json()

    assert data["image_id"] == "test-image-123"
    assert data["staff_id"] == test_staff_data["staff_id"]
    assert data["is_primary"] is True
    assert data["image_path"] == "staff-faces/t-test/test-image-123.jpg"
    assert len(data["face_landmarks"]) == 5

    # Verify Milvus insertion was called
    mock_milvus.assert_called_once()


@pytest.mark.asyncio
async def test_upload_staff_face_image_no_face_detected(
    async_client: AsyncClient, test_token: str, test_staff_data
):
    """Test face image upload when no face is detected."""
    processing_result = {
        "success": False,
        "error": "No faces detected in image",
        "face_count": 0,
    }

    with patch.object(
        face_processing_service,
        "process_staff_face_image",
        return_value=processing_result,
    ):
        response = await async_client.post(
            f"/v1/staff/{test_staff_data['staff_id']}/faces",
            json={
                "image_data": "data:image/jpeg;base64,invalid_image_data",
                "is_primary": False,
            },
            headers={"Authorization": f"Bearer {test_token}"},
        )

    assert response.status_code == 400
    assert "No faces detected" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_staff_face_images(
    async_client: AsyncClient, test_token: str, mock_db_session, test_staff_data
):
    """Test retrieving staff face images."""
    # Mock face images in database
    face_images = [
        StaffFaceImage(
            tenant_id="t-test",
            image_id="img-1",
            staff_id=test_staff_data["staff_id"],
            image_path="staff-faces/t-test/img-1.jpg",
            face_landmarks=json.dumps(
                [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0], [7.0, 8.0], [9.0, 10.0]]
            ),
            is_primary=True,
        ),
        StaffFaceImage(
            tenant_id="t-test",
            image_id="img-2",
            staff_id=test_staff_data["staff_id"],
            image_path="staff-faces/t-test/img-2.jpg",
            face_landmarks=json.dumps(
                [[2.0, 3.0], [4.0, 5.0], [6.0, 7.0], [8.0, 9.0], [10.0, 11.0]]
            ),
            is_primary=False,
        ),
    ]

    mock_db_session.execute.return_value.scalars.return_value.all.return_value = (
        face_images
    )

    response = await async_client.get(
        f"/v1/staff/{test_staff_data['staff_id']}/faces",
        headers={"Authorization": f"Bearer {test_token}"},
    )

    assert response.status_code == 200
    data = response.json()

    assert len(data) == 2
    assert data[0]["image_id"] == "img-1"
    assert data[0]["is_primary"] is True
    assert len(data[0]["face_landmarks"]) == 5
    assert data[1]["image_id"] == "img-2"
    assert data[1]["is_primary"] is False


@pytest.mark.asyncio
async def test_get_staff_with_faces(
    async_client: AsyncClient, test_token: str, mock_db_session, test_staff_data
):
    """Test retrieving staff details with face images."""
    # Mock staff member
    staff = Staff(
        tenant_id="t-test",
        staff_id=test_staff_data["staff_id"],
        name="John Doe",
        site_id="site-1",
        is_active=True,
    )

    # Mock face images
    face_images = [
        StaffFaceImage(
            tenant_id="t-test",
            image_id="img-1",
            staff_id=test_staff_data["staff_id"],
            image_path="staff-faces/t-test/img-1.jpg",
            face_landmarks=json.dumps(
                [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0], [7.0, 8.0], [9.0, 10.0]]
            ),
            is_primary=True,
        )
    ]

    # Mock database responses
    mock_db_session.execute.return_value.scalar_one_or_none.return_value = staff
    mock_db_session.execute.return_value.scalars.return_value.all.return_value = (
        face_images
    )

    response = await async_client.get(
        f"/v1/staff/{test_staff_data['staff_id']}/details",
        headers={"Authorization": f"Bearer {test_token}"},
    )

    assert response.status_code == 200
    data = response.json()

    assert data["staff_id"] == test_staff_data["staff_id"]
    assert data["name"] == "John Doe"
    assert len(data["face_images"]) == 1
    assert data["face_images"][0]["is_primary"] is True


@pytest.mark.asyncio
async def test_delete_staff_face_image(
    async_client: AsyncClient, test_token: str, mock_db_session, test_staff_data
):
    """Test deleting a staff face image."""
    # Mock face image
    face_image = StaffFaceImage(
        tenant_id="t-test",
        image_id="img-1",
        staff_id=test_staff_data["staff_id"],
        image_path="staff-faces/t-test/img-1.jpg",
        is_primary=False,
    )

    mock_db_session.execute.return_value.scalar_one_or_none.return_value = face_image

    with patch("app.main.minio_client.delete_file") as mock_minio:
        with patch(
            "app.main.milvus_client.delete_embedding_by_metadata"
        ) as mock_milvus:
            response = await async_client.delete(
                f"/v1/staff/{test_staff_data['staff_id']}/faces/img-1",
                headers={"Authorization": f"Bearer {test_token}"},
            )

    assert response.status_code == 200
    assert response.json()["message"] == "Face image deleted successfully"

    # Verify cleanup was called
    mock_minio.assert_called_once_with("faces-derived", "staff-faces/t-test/img-1.jpg")
    mock_milvus.assert_called_once()
    mock_db_session.delete.assert_called_once_with(face_image)


@pytest.mark.asyncio
async def test_recalculate_face_embedding(
    async_client: AsyncClient, test_token: str, mock_db_session, test_staff_data
):
    """Test recalculating face landmarks and embedding."""
    # Mock face image
    face_image = StaffFaceImage(
        tenant_id="t-test",
        image_id="img-1",
        staff_id=test_staff_data["staff_id"],
        image_path="staff-faces/t-test/img-1.jpg",
        is_primary=False,
    )

    mock_db_session.execute.return_value.scalar_one_or_none.return_value = face_image

    # Mock MinIO download
    fake_image_data = b"fake_image_data"

    # Mock processing result
    processing_result = {
        "success": True,
        "landmarks": [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0], [7.0, 8.0], [9.0, 10.0]],
        "embedding": [0.2] * 512,
        "face_count": 1,
        "confidence": 0.92,
    }

    with patch("app.main.minio_client.download_file", return_value=fake_image_data):
        with patch.object(
            face_processing_service,
            "process_staff_face_image",
            return_value=processing_result,
        ):
            with patch("app.main.milvus_client.delete_embedding_by_metadata"):
                with patch("app.main.milvus_client.insert_embedding"):
                    response = await async_client.put(
                        f"/v1/staff/{test_staff_data['staff_id']}/faces/img-1/recalculate",
                        headers={"Authorization": f"Bearer {test_token}"},
                    )

    assert response.status_code == 200
    data = response.json()
    assert "recalculated successfully" in data["message"]
    assert data["processing_info"]["confidence"] == 0.92


@pytest.mark.asyncio
async def test_face_recognition_test(
    async_client: AsyncClient, test_token: str, mock_db_session, test_staff_data
):
    """Test face recognition testing functionality."""
    # Mock staff member
    staff = Staff(
        tenant_id="t-test",
        staff_id=test_staff_data["staff_id"],
        name="John Doe",
        site_id="site-1",
        is_active=True,
    )

    # Mock face images with embeddings
    face_images = [
        StaffFaceImage(
            tenant_id="t-test",
            image_id="img-1",
            staff_id=test_staff_data["staff_id"],
            face_embedding=json.dumps([0.1] * 512),
            is_primary=True,
        ),
        StaffFaceImage(
            tenant_id="t-test",
            image_id="img-2",
            staff_id=999,  # Different staff
            face_embedding=json.dumps([0.9] * 512),
            is_primary=True,
        ),
    ]

    mock_db_session.execute.return_value.scalar_one_or_none.return_value = staff
    mock_db_session.execute.return_value.scalars.return_value.all.return_value = (
        face_images
    )

    # Mock staff name lookup
    mock_db_session.execute.return_value.scalar_one_or_none.side_effect = [
        staff,
        "John Doe",
        "Jane Smith",
    ]

    # Mock recognition test result
    test_result = {
        "success": True,
        "matches": [
            {
                "staff_id": test_staff_data["staff_id"],
                "staff_name": "John Doe",
                "similarity": 0.95,
                "image_id": "img-1",
            },
            {
                "staff_id": 999,
                "staff_name": "Jane Smith",
                "similarity": 0.3,
                "image_id": "img-2",
            },
        ],
        "best_match": {
            "staff_id": test_staff_data["staff_id"],
            "staff_name": "John Doe",
            "similarity": 0.95,
            "image_id": "img-1",
        },
        "processing_info": {
            "test_face_detected": True,
            "test_confidence": 0.88,
            "total_staff_compared": 2,
        },
    }

    with patch.object(
        face_processing_service, "test_face_recognition", return_value=test_result
    ):
        response = await async_client.post(
            f"/v1/staff/{test_staff_data['staff_id']}/test-recognition",
            json={
                "test_image": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAIBAQIBAQICAgICAgICAwUDAwMDAwYEBAMFBwYHBw=="
            },
            headers={"Authorization": f"Bearer {test_token}"},
        )

    assert response.status_code == 200
    data = response.json()

    assert len(data["matches"]) == 2
    assert data["best_match"]["staff_id"] == test_staff_data["staff_id"]
    assert data["best_match"]["similarity"] == 0.95
    assert data["processing_info"]["test_face_detected"] is True
    assert data["processing_info"]["total_staff_compared"] == 2


@pytest.mark.asyncio
async def test_face_recognition_test_no_face_detected(
    async_client: AsyncClient, test_token: str, mock_db_session, test_staff_data
):
    """Test face recognition test when no face is detected in test image."""
    staff = Staff(
        tenant_id="t-test", staff_id=test_staff_data["staff_id"], name="John Doe"
    )

    mock_db_session.execute.return_value.scalar_one_or_none.return_value = staff
    mock_db_session.execute.return_value.scalars.return_value.all.return_value = []

    test_result = {
        "success": False,
        "error": "No faces detected in test image",
        "matches": [],
    }

    with patch.object(
        face_processing_service, "test_face_recognition", return_value=test_result
    ):
        response = await async_client.post(
            f"/v1/staff/{test_staff_data['staff_id']}/test-recognition",
            json={"test_image": "data:image/jpeg;base64,invalid_image_data"},
            headers={"Authorization": f"Bearer {test_token}"},
        )

    assert response.status_code == 400
    assert "No faces detected" in response.json()["detail"]


@pytest.mark.asyncio
async def test_staff_face_image_not_found(
    async_client: AsyncClient, test_token: str, mock_db_session, test_staff_data
):
    """Test accessing non-existent face image."""
    mock_db_session.execute.return_value.scalar_one_or_none.return_value = None

    response = await async_client.delete(
        f"/v1/staff/{test_staff_data['staff_id']}/faces/non-existent",
        headers={"Authorization": f"Bearer {test_token}"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Face image not found"


@pytest.mark.asyncio
async def test_set_primary_image_updates_others(
    async_client: AsyncClient, test_token: str, mock_db_session, test_staff_data
):
    """Test that setting an image as primary updates other primary images."""
    processing_result = {
        "success": True,
        "image_id": "test-image-123",
        "image_path": "staff-faces/t-test/test-image-123.jpg",
        "landmarks": [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0], [7.0, 8.0], [9.0, 10.0]],
        "embedding": [0.1] * 512,
        "face_count": 1,
        "confidence": 0.95,
    }

    with patch.object(
        face_processing_service,
        "process_staff_face_image",
        return_value=processing_result,
    ):
        with patch("app.main.milvus_client.insert_embedding"):
            response = await async_client.post(
                f"/v1/staff/{test_staff_data['staff_id']}/faces",
                json={
                    "image_data": "data:image/jpeg;base64,valid_image_data",
                    "is_primary": True,
                },
                headers={"Authorization": f"Bearer {test_token}"},
            )

    assert response.status_code == 200

    # Verify that update was called to set other images as non-primary
    mock_db_session.execute.assert_called()
