"""Database initialization utility for development."""

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from ..core.config import settings
from ..models.database import Base, Camera, CameraType, Site, Tenant, User, UserRole

logger = logging.getLogger(__name__)


async def init_database(drop_existing: bool = False) -> None:
    """Initialize database with tables and default data.

    Args:
        drop_existing: If True, drop all existing tables first
    """
    logger.info("Initializing database...")

    # Create async engine for initialization
    engine = create_async_engine(settings.database_url, echo=settings.database_echo)

    try:
        async with engine.begin() as conn:
            if drop_existing:
                logger.info("Dropping existing tables...")
                await conn.run_sync(Base.metadata.drop_all)

            logger.info("Creating database tables...")
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully")

        # Create default data
        await create_default_data(engine)

    finally:
        await engine.dispose()


async def create_default_data(engine) -> None:
    """Create default system data."""
    logger.info("Creating default system data...")

    async with AsyncSession(engine) as session:
        try:
            # Check if system admin already exists
            from sqlalchemy import select

            result = await session.execute(
                select(User).where(User.role == UserRole.SYSTEM_ADMIN).limit(1)
            )
            existing_admin = result.scalar_one_or_none()

            if not existing_admin:
                # Create system admin user
                admin = User(
                    username="admin",
                    email="admin@system.local",
                    first_name="System",
                    last_name="Administrator",
                    role=UserRole.SYSTEM_ADMIN,
                    is_active=True,
                    is_email_verified=True,
                )
                admin.set_password("admin123")
                session.add(admin)

                logger.info(
                    "Created default system admin user (username: admin, password: admin123)"
                )

            # Create default development tenant if not exists
            result = await session.execute(
                select(Tenant).where(Tenant.tenant_id == "t-dev").limit(1)
            )
            existing_tenant = result.scalar_one_or_none()

            if not existing_tenant:
                dev_tenant = Tenant(
                    tenant_id="t-dev", name="Development Tenant", is_active=True
                )
                session.add(dev_tenant)
                logger.info("Created default development tenant (t-dev)")

            # Create default development site if not exists
            result = await session.execute(
                select(Site).where(Site.tenant_id == "t-dev").limit(1)
            )
            existing_site = result.scalar_one_or_none()

            if not existing_site:
                dev_site = Site(
                    tenant_id="t-dev",
                    name="Development Site",
                    location="Local Development Environment",
                    is_active=True,
                )
                session.add(dev_site)
                await session.flush()  # Get the site_id
                logger.info(
                    f"Created default development site (ID: {dev_site.site_id})"
                )

                # Create default webcam cameras for development
                cameras = [
                    Camera(
                        tenant_id="t-dev",
                        site_id=dev_site.site_id,
                        name="USB Webcam",
                        camera_type=CameraType.WEBCAM,
                        device_index=0,
                        is_active=True,
                    ),
                    Camera(
                        tenant_id="t-dev",
                        site_id=dev_site.site_id,
                        name="Built-in Webcam",
                        camera_type=CameraType.WEBCAM,
                        device_index=1,
                        is_active=True,
                    ),
                    Camera(
                        tenant_id="t-dev",
                        site_id=dev_site.site_id,
                        name="External Webcam",
                        camera_type=CameraType.WEBCAM,
                        device_index=2,
                        is_active=True,
                    ),
                ]

                for camera in cameras:
                    session.add(camera)

                logger.info(
                    "Created default development cameras (USB, Built-in, External)"
                )

            await session.commit()
            logger.info("Default system data created successfully")

        except Exception as e:
            await session.rollback()
            logger.error(f"Failed to create default data: {e}")
            raise


async def reset_database() -> None:
    """Drop and recreate the entire database."""
    logger.info("Resetting database (drop and recreate)...")
    await init_database(drop_existing=True)
    logger.info("Database reset completed")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Database initialization utility")
    parser.add_argument(
        "--reset", action="store_true", help="Drop and recreate all tables"
    )
    parser.add_argument(
        "--init", action="store_true", help="Create tables if they don't exist"
    )
    args = parser.parse_args()

    if args.reset:
        asyncio.run(reset_database())
    elif args.init:
        asyncio.run(init_database(drop_existing=False))
    else:
        print("Use --init to create tables or --reset to drop and recreate all tables")
