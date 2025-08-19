from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

from .config import settings


class Database:
    def __init__(self):
        self.engine = create_async_engine(
            settings.database_url,
            pool_pre_ping=True,
            pool_recycle=300,
        )
        self.session_maker = sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def close(self):
        if self.engine:
            await self.engine.dispose()

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