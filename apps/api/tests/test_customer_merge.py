import pytest
from fastapi.testclient import TestClient

from apps.api.app.main import app


def test_merge_noop_same_customer(admin_token):
    client = TestClient(app)
    payload = {
        "primary_customer_id": 123,
        "secondary_customer_id": 123,
        "notes": "duplicate record"
    }
    headers = {"Authorization": f"Bearer {admin_token}"}
    r = client.post("/v1/customers/merge", json=payload, headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["message"].startswith("No-op")
    assert data["primary_customer_id"] == 123
    assert data["secondary_customer_id"] == 123
