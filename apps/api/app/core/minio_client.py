from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from minio import Minio
from minio.lifecycleconfig import LifecycleConfig, Rule, Expiration

from .config import settings

logger = logging.getLogger(__name__)


class MinIOClient:
    def __init__(self):
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=False,  # Use HTTPS in production
        )
        self.bucket_raw = settings.minio_bucket_raw
        self.bucket_derived = settings.minio_bucket_derived

    async def setup_buckets(self):
        """Create buckets and set lifecycle policies"""
        try:
            # Create buckets if they don't exist
            for bucket in [self.bucket_raw, self.bucket_derived]:
                if not self.client.bucket_exists(bucket):
                    self.client.make_bucket(bucket)
                    logger.info(f"Created MinIO bucket: {bucket}")

            # Set lifecycle policy for raw bucket (30-day retention)
            lifecycle_config = LifecycleConfig(
                [
                    Rule(
                        rule_id="delete-raw-after-30-days",
                        status="Enabled",
                        expiration=Expiration(days=30),
                    )
                ]
            )
            self.client.set_bucket_lifecycle(self.bucket_raw, lifecycle_config)
            logger.info(f"Set 30-day lifecycle policy on {self.bucket_raw}")

        except Exception as e:
            logger.error(f"Failed to setup MinIO buckets: {e}")
            raise

    def upload_image(
        self, 
        bucket: str, 
        object_name: str, 
        data: bytes, 
        content_type: str = "image/jpeg"
    ) -> str:
        """Upload image data to MinIO bucket"""
        try:
            from io import BytesIO
            
            self.client.put_object(
                bucket,
                object_name,
                BytesIO(data),
                length=len(data),
                content_type=content_type,
            )
            return f"s3://{bucket}/{object_name}"
        except Exception as e:
            logger.error(f"Failed to upload image {object_name}: {e}")
            raise

    def get_presigned_url(
        self, 
        bucket: str, 
        object_name: str, 
        expiry: timedelta = timedelta(hours=1)
    ) -> str:
        """Generate presigned URL for object access"""
        try:
            return self.client.presigned_get_object(bucket, object_name, expires=expiry)
        except Exception as e:
            logger.error(f"Failed to generate presigned URL for {object_name}: {e}")
            raise

    def get_presigned_put_url(
        self, 
        bucket: str, 
        object_name: str, 
        expiry: timedelta = timedelta(hours=1)
    ) -> str:
        """Generate presigned URL for uploading objects"""
        try:
            return self.client.presigned_put_object(bucket, object_name, expires=expiry)
        except Exception as e:
            logger.error(f"Failed to generate presigned PUT URL for {object_name}: {e}")
            raise

    def delete_object(self, bucket: str, object_name: str) -> bool:
        """Delete an object from bucket"""
        try:
            self.client.remove_object(bucket, object_name)
            return True
        except Exception as e:
            logger.error(f"Failed to delete object {object_name}: {e}")
            return False

    def object_exists(self, bucket: str, object_name: str) -> bool:
        """Check if object exists in bucket"""
        try:
            self.client.stat_object(bucket, object_name)
            return True
        except Exception:
            return False


# Global MinIO client instance
minio_client = MinIOClient()