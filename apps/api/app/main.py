from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from .core.config import settings
from .core.database import get_db_session, db
from .core.middleware import tenant_context_middleware
from .core.milvus_client import milvus_client
from .core.minio_client import minio_client
from .models.database import Camera
from .services.camera_proxy_service import camera_proxy_service
from .services.worker_monitor_service import worker_monitor_service
from .services.worker_registry import worker_registry
from .services.worker_command_service import worker_command_service
from .services.camera_delegation_service import camera_delegation_service
from .core.task_manager import task_manager
from .routers import health, auth, tenants, sites, cameras, staff, customers, events, files, workers, worker_registry as worker_registry_router, worker_camera_management, lease_management


async def initialize_camera_proxy():
    """Initialize camera proxy service for worker delegation"""
    try:
        await camera_proxy_service.initialize()
        logging.info("Camera proxy service initialized - cameras are managed by workers")
    except Exception as e:
        logging.error(f"Failed to initialize camera proxy service: {e}")


# Application lifespan management
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        await milvus_client.connect()
        logging.info("Connected to Milvus")
    except Exception as e:
        logging.warning(f"Failed to connect to Milvus: {e}")
    
    try:
        await minio_client.setup_buckets()
        logging.info("Connected to MinIO")
    except Exception as e:
        logging.warning(f"Failed to connect to MinIO: {e}")
    
    # Initialize camera proxy service
    await initialize_camera_proxy()
    
    # Start task manager
    await task_manager.start()
    logging.info("Task manager started")
    
    # Start worker monitoring service
    try:
        await worker_monitor_service.start()
        logging.info("Started worker monitoring service")
    except Exception as e:
        logging.warning(f"Failed to start worker monitoring service: {e}")
    
    # Start worker registry service
    try:
        await worker_registry.start()
        logging.info("Started worker registry service")
    except Exception as e:
        logging.warning(f"Failed to start worker registry service: {e}")
    
    # Start worker command service
    try:
        await worker_command_service.start()
        logging.info("Started worker command service")
    except Exception as e:
        logging.warning(f"Failed to start worker command service: {e}")
    
    # Start camera delegation service
    try:
        await camera_delegation_service.start()
        logging.info("Started camera delegation service")
    except Exception as e:
        logging.warning(f"Failed to start camera delegation service: {e}")
    
    # Start assignment service (lease-based delegation)
    try:
        from .services.assignment_service import assignment_service
        await assignment_service.start()
        logging.info("Started lease-based assignment service")
    except Exception as e:
        logging.warning(f"Failed to start assignment service: {e}")
    
    logging.info("API startup completed")
    
    yield
    
    # Shutdown - execute cleanup operations concurrently with timeouts
    logging.info("Starting graceful shutdown...")
    
    # Create shutdown tasks with timeouts
    async def cleanup_cameras():
        try:
            await camera_proxy_service.shutdown()
            logging.info("Cleaned up camera proxy service")
        except Exception as e:
            logging.error(f"Failed to cleanup camera proxy service: {e}")
    
    # Service cleanup task  
    async def cleanup_services():
        try:
            await task_manager.stop()
            await worker_monitor_service.stop()
            await worker_registry.stop()
            await worker_command_service.stop()
            await camera_delegation_service.stop()
            await milvus_client.disconnect()
            await db.close()
            logging.info("Successfully disconnected from services")
        except Exception as e:
            logging.error(f"Error during service shutdown: {e}")
    
    # Run cleanup tasks with timeout
    try:
        await asyncio.wait_for(
            asyncio.gather(
                cleanup_cameras(),
                cleanup_services(),
                return_exceptions=True
            ),
            timeout=3.0  # 3 second total shutdown timeout
        )
    except asyncio.TimeoutError:
        logging.warning("Shutdown timeout reached, forcing exit")
    except Exception as e:
        logging.error(f"Error during shutdown: {e}")
    
    logging.info("Shutdown completed")


app = FastAPI(
    title="Customer Visits API",
    version="0.1.0",
    openapi_url="/v1/openapi.json",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.middleware("http")(tenant_context_middleware)

# Include routers
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(tenants.router)
app.include_router(sites.router)
app.include_router(cameras.router)
app.include_router(staff.router)
app.include_router(customers.router)
app.include_router(events.router)
app.include_router(files.router)
app.include_router(workers.router)
app.include_router(worker_registry_router.router)
app.include_router(worker_camera_management.router)
app.include_router(lease_management.router)


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port)