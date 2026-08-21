import boto3
import os
import tempfile
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

storage_client = StorageClient()
