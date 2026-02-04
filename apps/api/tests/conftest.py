import asyncio
import os
from pathlib import Path
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

# Set test environment variables before importing app
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:////tmp/customer_visit_test.db"
os.environ["ENV"] = "test"

from apps.api.app.core.database import get_db, get_db_session
from apps.api.app.main import app
from apps.api.app.models.database import Base


@pytest.fixture
def db_context(tmp_path: Path):
    """Create per-test database engines and session makers."""
    db_file = tmp_path / "test.db"
    sync_url = f"sqlite:///{db_file}"
    async_url = f"sqlite+aiosqlite:///{db_file}"

    sync_engine = create_engine(sync_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=sync_engine)

    async_engine = create_async_engine(async_url)
    async_session_maker = sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )
    sync_session_maker = sessionmaker(sync_engine, class_=Session, expire_on_commit=False)

    yield {
        "async_engine": async_engine,
        "sync_engine": sync_engine,
        "async_session_maker": async_session_maker,
        "sync_session_maker": sync_session_maker,
    }

    sync_engine.dispose()


@pytest.fixture
async def db_session(db_context) -> AsyncGenerator[AsyncSession, None]:
    """Create async database session."""
    async_session = db_context["async_session_maker"]
    async with async_session() as session:
        yield session
    await db_context["async_engine"].dispose()


@pytest.fixture
def sync_db_session(db_context) -> Generator[Session, None, None]:
    """Create sync database session."""
    sync_session = db_context["sync_session_maker"]
    session = sync_session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Mock AsyncSession for API tests that stub database access."""
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
async def async_client(db_session, sync_db_session):
    """Async HTTP client with database dependency overrides."""

    async def override_get_db_session():
        yield db_session

    def override_get_db():
        try:
            yield sync_db_session
        finally:
            pass

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
async def async_client_mock_db(mock_db_session):
    """Async HTTP client that uses a mocked async DB session."""

    async def override_get_db_session():
        yield mock_db_session

    app.dependency_overrides[get_db_session] = override_get_db_session

    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

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


@pytest.fixture
def test_token():
    """Tenant admin token for testing."""
    from apps.api.app.core.security import mint_jwt

    return mint_jwt(sub="tester", role="tenant_admin", tenant_id="t-test")


@pytest.fixture
def test_staff_data():
    """Sample staff fixture data."""
    return {"staff_id": 1, "tenant_id": "t-test", "site_id": 1}
