from fastapi.testclient import TestClient
from apps.api.app.main import app


def test_health():
    client = TestClient(app)
    r = client.get("/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_token_and_me():
    client = TestClient(app)
    r = client.post(
        "/v1/auth/token",
        json={"grant_type": "api_key", "api_key": "dev-api-key", "tenant_id": "t1", "role": "system_admin"},
    )
    assert r.status_code == 200
    token = r.json()["access_token"]
    r2 = client.get("/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200
    assert r2.json()["tenant_id"] == "t1"

