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
from .services.camera_streaming_service import streaming_service
from .services.worker_monitor_service import worker_monitor_service
from .routers import health, auth, tenants, sites, cameras, staff, customers, events, files, workers


async def auto_start_camera_streams():
    """Auto-start all active camera streams on API startup"""
    try:
        async for db_session in get_db_session():
            try:
                # Get all active cameras across all tenants
                result = await db_session.execute(
                    select(Camera).where(Camera.is_active == True)
                )
                cameras = result.scalars().all()
                
                started_count = 0
                for camera in cameras:
                    success = streaming_service.start_stream(
                        camera_id=camera.camera_id,
                        camera_type=camera.camera_type.value,
                        rtsp_url=camera.rtsp_url,
                        device_index=camera.device_index
                    )
                    if success:
                        started_count += 1
                        logging.info(f"Auto-started stream for camera {camera.camera_id}")
                    else:
                        logging.warning(f"Failed to auto-start stream for camera {camera.camera_id}")
                
                logging.info(f"Auto-started {started_count} camera streams")
                break  # Only use the first database session
                
            except Exception as e:
                logging.error(f"Error auto-starting camera streams: {e}")
                break
                
    except Exception as e:
        logging.error(f"Failed to get database session for auto-start: {e}")


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
    
    # Auto-start all active camera streams
    try:
        await auto_start_camera_streams()
        logging.info("Auto-started camera streams")
    except Exception as e:
        logging.warning(f"Failed to auto-start camera streams: {e}")
    
    # Start worker monitoring service
    try:
        await worker_monitor_service.start()
        logging.info("Started worker monitoring service")
    except Exception as e:
        logging.warning(f"Failed to start worker monitoring service: {e}")
    
    logging.info("API startup completed")
    
    yield
    
    # Shutdown - execute cleanup operations concurrently with timeouts
    logging.info("Starting graceful shutdown...")
    
    # Create shutdown tasks with timeouts
    async def cleanup_cameras():
        try:
            streaming_service.cleanup_all_streams()
            logging.info("Cleaned up camera streams")
        except Exception as e:
            logging.error(f"Failed to cleanup camera streams: {e}")
    
    # Service cleanup task  
    async def cleanup_services():
        try:
            await worker_monitor_service.stop()
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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port)