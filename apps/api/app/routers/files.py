from typing import Optional

from datetime import timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Header, Depends
from fastapi.responses import Response
from pydantic import BaseModel

from ..core.minio_client import minio_client
from ..core.security import verify_jwt, get_current_user

router = APIRouter(prefix="/v1", tags=["File Management"])


class FileUploadRequest(BaseModel):
    filename: str
    content_type: str = "image/jpeg"


class FileDownloadRequest(BaseModel):
    filename: str


class FileUrlResponse(BaseModel):
    upload_url: str
    filename: str


class FileDownloadResponse(BaseModel):
    download_url: str
    filename: str


@router.post("/files/upload-url", response_model=FileUrlResponse)
async def get_upload_url(
    request: FileUploadRequest,
    user: dict = Depends(get_current_user)
):
    """Generate a presigned URL for uploading files to MinIO"""
    try:
        # Validate filename to prevent path traversal
        if ".." in request.filename or request.filename.startswith("/"):
            raise HTTPException(status_code=400, detail="Invalid filename")
        
        # Ensure the file goes into the tenant's folder
        if not request.filename.startswith("faces-raw/"):
            request.filename = f"faces-raw/{request.filename}"
        
        # Generate presigned upload URL (valid for 1 hour)
        upload_url = minio_client.get_presigned_put_url(
            bucket="faces-raw",
            object_name=request.filename.replace("faces-raw/", ""),
            expiry=timedelta(hours=1)
        )
        
        return FileUrlResponse(
            upload_url=upload_url,
            filename=request.filename
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate upload URL: {str(e)}")


@router.post("/files/download-url", response_model=FileDownloadResponse)
async def get_download_url(
    request: FileDownloadRequest,
    user: dict = Depends(get_current_user)
):
    """Generate a presigned URL for downloading files from MinIO"""
    try:
        # Validate filename to prevent path traversal
        if ".." in request.filename or request.filename.startswith("/"):
            raise HTTPException(status_code=400, detail="Invalid filename")
        
        # Determine bucket and object name from filename
        if request.filename.startswith("faces-raw/"):
            bucket = "faces-raw"
            object_name = request.filename.replace("faces-raw/", "")
        elif request.filename.startswith("staff-faces/"):
            bucket = "faces-derived"
            object_name = request.filename.replace("staff-faces/", "")
        else:
            # Default to faces-raw bucket
            bucket = "faces-raw"
            object_name = request.filename
        
        # Generate presigned download URL (valid for 1 hour)
        download_url = minio_client.get_presigned_url(
            bucket=bucket,
            object_name=object_name,
            expiry=timedelta(hours=1)
        )
        
        return FileDownloadResponse(
            download_url=download_url,
            filename=request.filename
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate download URL: {str(e)}")




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

    # Handle different secure file types with proper tenant isolation
    bucket = None
    object_path = None
    
    if file_path.startswith("staff-faces/"):
        # Staff face images: staff-faces/{tenant_id}/filename
        parts = file_path.split("/")
        if len(parts) < 3:
            raise HTTPException(status_code=404, detail="File not found")
        
        path_tenant_id = parts[1]
        if path_tenant_id != payload.get("tenant_id"):
            raise HTTPException(status_code=403, detail="Forbidden")
        
        bucket = "faces-derived"
        object_path = file_path
        
    elif file_path.startswith("worker-faces/"):
        # Worker uploaded face images: worker-faces/filename  
        # These are from faces-raw bucket, require authentication but no tenant isolation
        bucket = "faces-raw"
        object_path = file_path.replace("worker-faces/", "")
        
    elif file_path.startswith("visits-faces/"):
        # API-generated face crops: visits-faces/generated/filename
        # These are from faces-derived bucket, require authentication but no tenant isolation 
        bucket = "faces-derived"
        object_path = file_path.replace("visits-faces/", "")
        
    else:
        # Only allow specific secure path types
        raise HTTPException(status_code=404, detail="File not found")

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
        data = await minio_client.download_file(bucket, object_path)
        return Response(content=data, media_type=content_type)
    except Exception as e:
        logger.warning(f"Failed to serve file {file_path}: {e}")
        raise HTTPException(status_code=404, detail="File not found")