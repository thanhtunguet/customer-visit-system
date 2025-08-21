from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Header
from fastapi.responses import Response

from ..core.minio_client import minio_client
from ..core.security import verify_jwt

router = APIRouter(prefix="/v1", tags=["File Management"])


@router.get("/files/{file_path:path}")
async def serve_file(
    file_path: str,
    token: Optional[str] = Query(None),
    access_token: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
):
    """Serve files stored in MinIO with tenant-aware access control.

    Currently supports staff face images under paths like:
    staff-faces/{tenant_id}/<filename>.{jpg|png|webp|gif}
    """
    # Authenticate via Authorization header or ?token / ?access_token query param
    jwt_token: Optional[str] = None
    if authorization and authorization.startswith("Bearer "):
        jwt_token = authorization.split(" ", 1)[1]
    elif token:
        jwt_token = token
    elif access_token:
        jwt_token = access_token
    else:
        raise HTTPException(status_code=401, detail="Missing token")

    payload = verify_jwt(jwt_token)
    # Basic validation
    if not file_path or ".." in file_path or file_path.startswith("/"):
        raise HTTPException(status_code=400, detail="Invalid file path")

    # Restrict to staff face images and enforce tenant isolation
    if not file_path.startswith("staff-faces/"):
        raise HTTPException(status_code=404, detail="File not found")

    parts = file_path.split("/")
    if len(parts) < 3:
        raise HTTPException(status_code=404, detail="File not found")

    path_tenant_id = parts[1]
    if path_tenant_id != payload.get("tenant_id"):
        raise HTTPException(status_code=403, detail="Forbidden")

    # Determine content type by extension
    content_type = "application/octet-stream"
    lower = file_path.lower()
    if lower.endswith(".jpg") or lower.endswith(".jpeg"):
        content_type = "image/jpeg"
    elif lower.endswith(".png"):
        content_type = "image/png"
    elif lower.endswith(".webp"):
        content_type = "image/webp"
    elif lower.endswith(".gif"):
        content_type = "image/gif"

    try:
        data = await minio_client.download_file("faces-derived", file_path)
        return Response(content=data, media_type=content_type)
    except Exception:
        raise HTTPException(status_code=404, detail="File not found")