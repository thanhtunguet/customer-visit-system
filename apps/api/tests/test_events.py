from fastapi.testclient import TestClient
from app.main import app


def test_ingest_face():
    client = TestClient(app)
    # Get token
    tok = client.post("/v1/auth/token", json={"grant_type": "api_key", "api_key": "dev-api-key", "tenant_id": "t1"}).json()["access_token"]
    evt = {
        "tenant_id": "t1",
        "site_id": "s1",
        "camera_id": "c1",
        "timestamp": "2024-01-01T00:00:00Z",
        "embedding": [0.0] * 512,
        "bbox": [0, 0, 10, 10],
        "is_staff_local": False,
    }
    r = client.post("/v1/events/face", json=evt, headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    body = r.json()
    assert body["tenant_id"] == "t1"

