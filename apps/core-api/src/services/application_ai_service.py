"""Internal AI service callers for resume parse and job-fit."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

import httpx

from src.config.settings import settings

__all__ = [
    "call_parse_resume",
    "call_match_resume_jd",
]


def _ai_url(path: str) -> str:
    return f"{settings.parsing_service_base_url}/{path.lstrip('/')}"


def _json_safe(value: object) -> object:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _http_error_detail(exc: httpx.HTTPError) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        body = (exc.response.text or "").strip()
        if body:
            return f"{exc.response.status_code} {body[:2000]}"
        return str(exc)
    return str(exc)


def call_parse_resume(*, s3_key: str, file_name: str) -> dict:
    payload = {
        "resume_name": file_name,
        "resume_path": s3_key,
    }
    try:
        with httpx.Client(timeout=300.0) as client:
            response = client.post(_ai_url("parse/resume"), json=payload)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ValueError(f"Resume parsing service unavailable: {_http_error_detail(exc)}") from exc

    data = response.json()
    if not isinstance(data, dict):
        raise ValueError("Invalid response from resume parsing service")
    return data


def call_match_resume_jd(
    *,
    application_id: UUID,
    job_id: UUID,
    parsed_jd: dict,
    parsed_resume: dict,
) -> dict:
    base = {
        "application_id": str(application_id),
        "job_id": str(job_id),
        # Preserve the parsed documents' semantics.  _json_safe only converts
        # values JSON cannot encode directly (for example Decimal and UUID).
        "parsed_jd": _json_safe(parsed_jd),
        "parsed_resume": _json_safe(parsed_resume),
    }
    try:
        with httpx.Client(timeout=120.0) as client:
            response = client.post(_ai_url("match/resume-jd"), json=base)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ValueError(f"Job-fit service unavailable: {_http_error_detail(exc)}") from exc

    data = response.json()
    if not isinstance(data, dict):
        raise ValueError("Invalid response from job-fit service")
    return data
