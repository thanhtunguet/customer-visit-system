from datetime import datetime, timezone

from fastapi import APIRouter

from ..core.config import settings
from ..core.milvus_client import milvus_client

router = APIRouter(prefix="/v1", tags=["Health & Monitoring"])


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "env": settings.env,
        "timestamp": datetime.now(timezone.utc),
    }


@router.get("/health/milvus")
async def health_milvus():
    """Get Milvus connection health status"""
    milvus_health = await milvus_client.health_check()
    return milvus_health


@router.get("/health/face-processing")
async def health_face_processing():
    """Check if face processing dependencies are available."""
    try:
        from ..services.face_processing_service import \
            FACE_PROCESSING_AVAILABLE

        return {
            "face_processing_available": FACE_PROCESSING_AVAILABLE,
            "status": "ready" if FACE_PROCESSING_AVAILABLE else "dependencies_missing",
            "message": (
                "Face processing is ready"
                if FACE_PROCESSING_AVAILABLE
                else "Install Pillow, OpenCV, and NumPy to enable face processing"
            ),
        }
    except Exception as e:
        return {
            "face_processing_available": False,
            "status": "error",
            "message": f"Error checking face processing status: {e}",
        }
