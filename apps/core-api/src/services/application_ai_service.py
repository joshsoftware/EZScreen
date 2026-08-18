"""Internal AI service callers for resume parse and job-fit."""

from __future__ import annotations

from uuid import UUID

import httpx

from src.config.settings import settings

__all__ = [
    "call_parse_resume",
    "call_match_resume_jd",
]


def _ai_url(path: str) -> str:
    return f"{settings.parsing_service_url.rstrip('/')}/{path.lstrip('/')}"


def call_parse_resume(*, s3_key: str, file_name: str) -> dict:
    payload = {
        "resume_name": file_name,
        "resume_path": s3_key,
    }
    try:
        with httpx.Client(timeout=120.0) as client:
            response = client.post(_ai_url("parse/resume"), json=payload)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ValueError(f"Resume parsing service unavailable: {exc}") from exc

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
    payload = {
        "application_id": str(application_id),
        "job_id": str(job_id),
        "parsed_resume": parsed_resume,
        "parsed_jd": parsed_jd,
    }
    try:
        with httpx.Client(timeout=120.0) as client:
            response = client.post(_ai_url("match/resume-jd"), json=payload)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ValueError(f"Job-fit service unavailable: {exc}") from exc

    data = response.json()
    if not isinstance(data, dict):
        raise ValueError("Invalid response from job-fit service")
    return data
