from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from .config import settings


class Database:
    def __init__(self):
        self.engine = create_async_engine(
            settings.database_url,
            pool_pre_ping=True,
            pool_recycle=300,
            pool_size=10,  # Limit concurrent connections
            max_overflow=20,  # Allow temporary overflow
            pool_timeout=30,  # Timeout for getting connections
            echo_pool=(
                True if getattr(settings, "log_level", "INFO") == "DEBUG" else False
            ),
        )
        self.session_maker = sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        # Synchronous engine for auth endpoints
        sync_url = settings.database_url.replace(
            "postgresql+asyncpg://", "postgresql+psycopg2://"
        )
        self.sync_engine = create_engine(
            sync_url,
            pool_pre_ping=True,
            pool_recycle=300,
            pool_size=5,  # Smaller pool for sync operations
            max_overflow=10,
            pool_timeout=30,
            echo_pool=(
                True if getattr(settings, "log_level", "INFO") == "DEBUG" else False
            ),
        )
        self.sync_session_maker = sessionmaker(
            self.sync_engine,
            expire_on_commit=False,
        )

    async def close(self):
        """Close database engine with timeout to prevent hanging"""
        if self.engine:
            try:
                # Use asyncio.wait_for to prevent hanging on dispose
                await asyncio.wait_for(self.engine.dispose(), timeout=2.0)
            except asyncio.TimeoutError:
                logging.warning("Database close timeout reached, forcing close")
            except Exception as e:
                logging.error(f"Error closing database: {e}")

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        async with self.session_maker() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    async def set_tenant_context(self, session: AsyncSession, tenant_id: str):
        """Set the tenant context for Row Level Security"""
        await session.execute(text(f"SET app.tenant_id = '{tenant_id}'"))


# Global database instance
db = Database()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database sessions"""
    async with db.get_session() as session:
        yield session


def get_db() -> Session:
    """FastAPI dependency for synchronous database sessions (for auth endpoints)"""
    session = db.sync_session_maker()
    try:
        yield session
    finally:
        session.close()
