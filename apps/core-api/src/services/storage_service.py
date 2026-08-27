"""S3/MinIO helpers for resume uploads."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone

from typing import Any, TypedDict

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from src.config.settings import settings

__all__ = [
    "ResumeObjectPayload",
    "build_resume_s3_key",
    "resume_key_prefix",
    "create_presigned_upload_url",
    "create_presigned_download_url",
    "get_resume_object",
    "guess_resume_content_type",
    "resume_display_name",
    "validate_resume_s3_key",
]

_UNSAFE_FILENAME = re.compile(r"[^a-zA-Z0-9._-]+")


class ResumeObjectPayload(TypedDict):
    body: Any
    content_type: str
    file_name: str
    content_length: int | None


def _s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def sanitize_file_name(file_name: str) -> str:
    base = file_name.strip().replace("\\", "/").rsplit("/", 1)[-1]
    safe = _UNSAFE_FILENAME.sub("-", base).strip("-")
    return safe or "resume"


def resume_key_prefix(organization_id: uuid.UUID, job_id: uuid.UUID) -> str:
    return f"orgs/{organization_id}/jobs/{job_id}/resumes/"


def build_resume_s3_key(
    organization_id: uuid.UUID,
    job_id: uuid.UUID,
    file_name: str,
) -> str:
    """orgs/{org}/jobs/{job}/resumes/{upload_id}-{file_name}"""
    upload_id = uuid.uuid4()
    stored_name = f"{upload_id}-{sanitize_file_name(file_name)}"
    return f"{resume_key_prefix(organization_id, job_id)}{stored_name}"


def validate_resume_s3_key(
    s3_key: str,
    *,
    organization_id: uuid.UUID,
    job_id: uuid.UUID,
) -> None:
    prefix = resume_key_prefix(organization_id, job_id)
    if not s3_key.startswith(prefix):
        raise ValueError(f"s3_key must start with {prefix}")
    remainder = s3_key[len(prefix) :]
    if not remainder or "/" in remainder:
        raise ValueError("Invalid s3_key path")


def create_presigned_upload_url(
    s3_key: str,
    content_type: str,
) -> tuple[str, datetime]:
    client = _s3_client()
    expires_in = settings.s3_presign_expires_seconds
    upload_url = client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.minio_bucket_resumes,
            "Key": s3_key,
            "ContentType": content_type,
        },
        ExpiresIn=expires_in,
    )
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    return upload_url, expires_at


def resume_display_name(s3_key: str) -> str:
    """Strip upload UUID prefix from stored key basename when present."""
    basename = s3_key.rsplit("/", 1)[-1]
    if len(basename) > 37 and basename[36] == "-":
        # {uuid}-{original}
        return basename[37:] or basename
    return basename or "resume"


def guess_resume_content_type(s3_key: str) -> str:
    lower = s3_key.lower()
    if lower.endswith(".docx"):
        return (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
    return "application/pdf"


def create_presigned_download_url(
    s3_key: str,
    *,
    disposition: str = "inline",
    file_name: str | None = None,
    content_type: str | None = None,
) -> tuple[str, datetime]:
    if disposition not in {"inline", "attachment"}:
        raise ValueError("disposition must be inline or attachment")

    display_name = file_name or resume_display_name(s3_key)
    resolved_type = content_type or guess_resume_content_type(s3_key)
    client = _s3_client()
    expires_in = settings.s3_presign_expires_seconds
    download_url = client.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": settings.minio_bucket_resumes,
            "Key": s3_key,
            "ResponseContentType": resolved_type,
            "ResponseContentDisposition": f'{disposition}; filename="{display_name}"',
        },
        ExpiresIn=expires_in,
    )
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    return download_url, expires_at


def get_resume_object(s3_key: str) -> ResumeObjectPayload:
    """Fetch resume bytes from object storage for same-origin proxying."""
    client = _s3_client()
    try:
        obj = client.get_object(
            Bucket=settings.minio_bucket_resumes,
            Key=s3_key,
        )
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "")
        if error_code in {"NoSuchKey", "404", "NotFound"}:
            raise LookupError("Resume file was not found in storage") from exc
        raise

    file_name = resume_display_name(s3_key)
    content_type = obj.get("ContentType") or guess_resume_content_type(s3_key)
    length = obj.get("ContentLength")
    return {
        "body": obj["Body"],
        "content_type": content_type,
        "file_name": file_name,
        "content_length": length if isinstance(length, int) else None,
    }
