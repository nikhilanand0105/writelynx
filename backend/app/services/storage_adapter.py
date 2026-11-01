import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, BinaryIO
import logging

from backend.app.core.config import settings

logger = logging.getLogger("writelynx.storage")


class StorageAdapter(ABC):
    @abstractmethod
    def save_file(self, source_path: Path, destination_key: str) -> str:
        """Store file artifact and return relative or canonical key."""
        pass

    @abstractmethod
    def read_file(self, storage_key: str) -> bytes:
        """Read artifact content bytes."""
        pass

    @abstractmethod
    def delete_file(self, storage_key: str) -> bool:
        """Securely remove artifact."""
        pass

    @abstractmethod
    def generate_presigned_download_url(self, storage_key: str, expires_in_seconds: int = 300) -> Optional[str]:
        """Generate short-lived authorized download link if supported."""
        pass


class LocalStorageAdapter(StorageAdapter):
    """Default local filesystem storage adapter."""

    def __init__(self, base_dir: Path = settings.STORAGE_DIR):
        self.base_dir = Path(base_dir)

    def _resolve_path(self, storage_key: str) -> Path:
        p = Path(storage_key)
        if p.is_absolute():
            return p
        return self.base_dir / storage_key

    def save_file(self, source_path: Path, destination_key: str) -> str:
        dest = self._resolve_path(destination_key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if source_path != dest:
            import shutil
            shutil.copy2(str(source_path), str(dest))
        return str(dest)

    def read_file(self, storage_key: str) -> bytes:
        path = self._resolve_path(storage_key)
        with open(path, "rb") as f:
            return f.read()

    def delete_file(self, storage_key: str) -> bool:
        path = self._resolve_path(storage_key)
        if path.exists():
            path.unlink(missing_ok=True)
            return True
        return False

    def generate_presigned_download_url(self, storage_key: str, expires_in_seconds: int = 300) -> Optional[str]:
        # Local storage serves through FastAPI FileResponse download endpoints
        return None


class CloudflareR2StorageAdapter(StorageAdapter):
    """
    Production private Cloudflare R2 object storage adapter.
    Uses S3-compatible API with zero egress fees and server-governed authorization.
    """

    def __init__(
        self,
        account_id: str,
        access_key_id: str,
        secret_access_key: str,
        bucket_name: str,
    ):
        import boto3
        from botocore.config import Config

        self.bucket_name = bucket_name
        self.endpoint_url = f"https://{account_id}.r2.cloudflarestorage.com"
        self.client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            config=Config(signature_version="s3v4"),
            region_name="auto",
        )

    def save_file(self, source_path: Path, destination_key: str) -> str:
        self.client.upload_file(str(source_path), self.bucket_name, destination_key)
        return destination_key

    def read_file(self, storage_key: str) -> bytes:
        response = self.client.get_object(Bucket=self.bucket_name, Key=storage_key)
        return response["Body"].read()

    def delete_file(self, storage_key: str) -> bool:
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=storage_key)
            return True
        except Exception as e:
            logger.error(f"Failed to delete object {storage_key} from R2: {e}")
            return False

    def generate_presigned_download_url(self, storage_key: str, expires_in_seconds: int = 300) -> Optional[str]:
        try:
            url = self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": storage_key},
                ExpiresIn=expires_in_seconds,
            )
            return url
        except Exception as e:
            logger.error(f"Failed to generate presigned URL for {storage_key}: {e}")
            return None


def get_storage_adapter() -> StorageAdapter:
    """Factory: selects Cloudflare R2 in cloud hosting if configured, otherwise local."""
    backend_choice = getattr(settings, "STORAGE_BACKEND", "local").lower()
    r2_account_id = os.getenv("R2_ACCOUNT_ID")
    r2_access_key = os.getenv("R2_ACCESS_KEY_ID")
    r2_secret_key = os.getenv("R2_SECRET_ACCESS_KEY")
    r2_bucket = os.getenv("R2_BUCKET_NAME", "writelynx-manuscripts")

    # If backend explicitly set to 'r2' or in production where R2 is expected
    if backend_choice == "r2" or (settings.ENVIRONMENT == "production" and (r2_account_id or r2_access_key)):
        if not (r2_account_id and r2_access_key and r2_secret_key):
            raise RuntimeError(
                "CRITICAL SECURITY BLOCKER: Cloudflare R2 credentials (R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY) must be fully configured when STORAGE_BACKEND=r2 or in production."
            )
        try:
            return CloudflareR2StorageAdapter(
                account_id=r2_account_id,
                access_key_id=r2_access_key,
                secret_access_key=r2_secret_key,
                bucket_name=r2_bucket,
            )
        except Exception as e:
            logger.error(f"Failed to initialize Cloudflare R2 storage adapter: {e}")
            raise RuntimeError(f"Cloudflare R2 storage initialization failed: {e}")

    # In dev/test, if R2 credentials provided, try R2
    if r2_account_id and r2_access_key and r2_secret_key:
        try:
            return CloudflareR2StorageAdapter(
                account_id=r2_account_id,
                access_key_id=r2_access_key,
                secret_access_key=r2_secret_key,
                bucket_name=r2_bucket,
            )
        except Exception as e:
            logger.warning(f"Failed to initialize Cloudflare R2 adapter, using local: {e}")

    return LocalStorageAdapter()
