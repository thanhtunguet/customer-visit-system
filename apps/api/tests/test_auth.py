import pytest
import jwt
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import mint_jwt, verify_jwt


client = TestClient(app)


def test_jwt_minting_and_verification():
    """Test JWT token creation and verification"""
    token = mint_jwt(
        sub="test-user",
        role="tenant_admin", 
        tenant_id="t-test",
        ttl_sec=3600
    )
    
    assert isinstance(token, str)
    assert len(token) > 0
    
    # Verify token
    payload = verify_jwt(token)
    assert payload["sub"] == "test-user"
    assert payload["role"] == "tenant_admin"
    assert payload["tenant_id"] == "t-test"


def test_api_key_authentication():
    """Test API key authentication flow"""
    response = client.post(
        "/v1/auth/token",
        json={
            "grant_type": "api_key",
            "api_key": "dev-api-key",
            "tenant_id": "t-test",
            "role": "worker"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_invalid_api_key():
    """Test invalid API key returns 401"""
    response = client.post(
        "/v1/auth/token",
        json={
            "grant_type": "api_key",
            "api_key": "invalid-key",
            "tenant_id": "t-test",
            "role": "worker"
        }
    )
    
    assert response.status_code == 401
    assert "Invalid API key" in response.json()["detail"]


def test_password_authentication():
    """Test password-based authentication (dev mode)"""
    response = client.post(
        "/v1/auth/token",
        json={
            "grant_type": "password",
            "username": "admin",
            "password": "password",
            "tenant_id": "t-test",
            "role": "tenant_admin"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data


def test_protected_endpoint_without_token():
    """Test protected endpoint returns 401 without token"""
    response = client.get("/v1/me")
    assert response.status_code == 401


def test_protected_endpoint_with_token():
    """Test protected endpoint works with valid token"""
    # Get token
    token_response = client.post(
        "/v1/auth/token",
        json={
            "grant_type": "api_key",
            "api_key": "dev-api-key",
            "tenant_id": "t-test",
            "role": "tenant_admin"
        }
    )
    token = token_response.json()["access_token"]
    
    # Use token
    response = client.get(
        "/v1/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["tenant_id"] == "t-test"
    assert data["role"] == "tenant_admin"