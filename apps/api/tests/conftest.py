import asyncio
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Set test environment variables before importing app
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["ENV"] = "test"

from apps.api.app.core.database import get_db_session
from apps.api.app.main import app
from apps.api.app.models.database import Base


@pytest.fixture(scope="session")
async def test_db():
    """Create test database"""
    # Create sync engine for table creation
    sync_engine = create_engine("sqlite:///:memory:", poolclass=StaticPool)
    Base.metadata.create_all(bind=sync_engine)

    # Create async engine for tests
    async_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", poolclass=StaticPool
    )

    yield async_engine

    await async_engine.dispose()


@pytest.fixture
async def db_session(test_db):
    """Create test database session"""
    async_session = sessionmaker(test_db, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session


@pytest.fixture
def client():
    """Create test client with mocked database"""

    async def mock_get_db():
        # Mock async session for TestClient
        from unittest.mock import AsyncMock

        mock_session = AsyncMock(spec=AsyncSession)
        yield mock_session

    app.dependency_overrides[get_db_session] = mock_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_tenant():
    """Sample tenant data for testing"""
    return {"tenant_id": "t-test", "name": "Test Tenant"}


@pytest.fixture
def sample_site():
    """Sample site data for testing"""
    return {"site_id": "s-test", "name": "Test Site", "location": "Test Location"}


@pytest.fixture
def admin_token():
    """Admin token for testing"""
    from apps.api.app.core.security import mint_jwt

    return mint_jwt(sub="admin", role="system_admin", tenant_id="t-test")
