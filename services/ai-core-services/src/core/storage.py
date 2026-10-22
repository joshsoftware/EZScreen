import boto3
import io
import os
import tempfile
from typing import Iterator

from boto3.s3.transfer import TransferConfig
from botocore.client import Config
from src.core.config import settings
from src.core.logger import logger

class StorageClient:
    def __init__(self):
        self.endpoint_url = f"http://{settings.minio_endpoint}"
        self.access_key = settings.minio_access_key
        self.secret_key = settings.minio_secret_key
        self.secure = settings.minio_secure
        self.default_bucket = settings.minio_bucket_name

        self.s3_client = boto3.client(
            's3',
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            config=Config(signature_version='s3v4'),
            verify=self.secure
        )
        logger.info(f"Initialized MinIO storage client targeting {self.endpoint_url}")

    def download_to_tempfile(self, s3_key: str, bucket_name: str = None) -> str:
        """
        Downloads a file from S3/MinIO and returns the path to a temporary file.
        The caller is responsible for deleting the temporary file.
        """
        bucket = bucket_name or self.default_bucket
        file_ext = os.path.splitext(s3_key)[1] if s3_key else ".pdf"
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
            tmp_path = tmp.name

        try:
            logger.info(f"Downloading s3://{bucket}/{s3_key} to {tmp_path}")
            self.s3_client.download_file(bucket, s3_key, tmp_path)
            return tmp_path
        except Exception as e:
            logger.error(f"Failed to download from S3: {str(e)}")
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise

    def upload_stream(
        self,
        chunks: Iterator[bytes],
        s3_key: str,
        *,
        bucket_name: str,
        content_type: str,
    ) -> None:
        """Multipart-upload an iterator of byte chunks without buffering the
        whole object (meeting recordings are 0.5-3 GB)."""
        self.s3_client.upload_fileobj(
            _ChunkReader(chunks),
            bucket_name,
            s3_key,
            ExtraArgs={"ContentType": content_type},
            Config=TransferConfig(multipart_chunksize=8 * 1024 * 1024, max_concurrency=2),
        )


class _ChunkReader(io.RawIOBase):
    """Expose an iterator of byte chunks as a readable file object."""

    def __init__(self, chunks: Iterator[bytes]):
        self._chunks = chunks
        self._buffer = b""

    def readable(self) -> bool:
        return True

    def readinto(self, target) -> int:
        while not self._buffer:
            try:
                self._buffer = next(self._chunks)
            except StopIteration:
                return 0
        size = min(len(target), len(self._buffer))
        target[:size] = self._buffer[:size]
        self._buffer = self._buffer[size:]
        return size


storage_client = StorageClient()
