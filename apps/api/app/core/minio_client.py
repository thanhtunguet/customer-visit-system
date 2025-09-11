from __future__ import annotations

import logging
from datetime import timedelta

try:
    from minio import Minio
    from minio.lifecycleconfig import Expiration, Filter, LifecycleConfig, Rule

    MINIO_AVAILABLE = True
except ImportError:
    MINIO_AVAILABLE = False

    class MockMinio:
        def __init__(self, *args, **kwargs):
            pass

        def bucket_exists(self, bucket):
            return True

        def make_bucket(self, bucket):
            pass

        def set_bucket_lifecycle(self, bucket, config):
            pass

    class MockLifecycleConfig:
        def __init__(self, *args):
            pass

    class MockRule:
        def __init__(self, *args, **kwargs):
            pass

    class MockExpiration:
        def __init__(self, *args):
            pass

    class MockFilter:
        def __init__(self, *args, **kwargs):
            pass

    # Assign mock classes to original names
    Minio = MockMinio  # type: ignore[misc,assignment]
    LifecycleConfig = MockLifecycleConfig  # type: ignore[misc,assignment]
    Rule = MockRule  # type: ignore[misc,assignment]
    Expiration = MockExpiration  # type: ignore[misc,assignment]
    Filter = MockFilter  # type: ignore[misc,assignment]


from .config import settings

logger = logging.getLogger(__name__)

if not MINIO_AVAILABLE:
    logger.warning("MinIO not available, using mock implementation")


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
        if not MINIO_AVAILABLE:
            logger.info("Using mock MinIO implementation for development")
            return

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
                        rule_filter=Filter(prefix=""),  # Apply to all objects in bucket
                        expiration=Expiration(days=30),
                    )
                ]
            )
            self.client.set_bucket_lifecycle(self.bucket_raw, lifecycle_config)
            logger.info(f"Set 30-day lifecycle policy on {self.bucket_raw}")

        except Exception as e:
            logger.warning(f"Failed to setup MinIO buckets (using mock): {e}")
            # Don't raise the exception, just log and continue with mock

    def upload_image(
        self,
        bucket: str,
        object_name: str,
        data: bytes,
        content_type: str = "image/jpeg",
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
        self, bucket: str, object_name: str, expiry: timedelta = timedelta(hours=1)
    ) -> str:
        """Generate presigned URL for object access"""
        try:
            return self.client.presigned_get_object(bucket, object_name, expires=expiry)
        except Exception as e:
            logger.error(f"Failed to generate presigned URL for {object_name}: {e}")
            raise

    def get_presigned_put_url(
        self, bucket: str, object_name: str, expiry: timedelta = timedelta(hours=1)
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

    async def download_file(self, bucket: str, object_name: str) -> bytes:
        """Download file data from MinIO bucket"""
        try:
            response = self.client.get_object(bucket, object_name)
            data = response.read()
            response.close()
            response.release_conn()
            return data
        except Exception as e:
            logger.error(f"Failed to download file {object_name}: {e}")
            raise

    async def delete_file(self, bucket: str, object_name: str) -> bool:
        """Delete a file from bucket (alias for delete_object)"""
        return self.delete_object(bucket, object_name)


# Global MinIO client instance
minio_client = MinIOClient()
