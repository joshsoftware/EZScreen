"""Internal AI service callers for resume parse and job-fit."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal
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


def _default_skill_years(parsed_jd: dict) -> float:
    experience = parsed_jd.get("experience_required")
    if isinstance(experience, dict):
        for key in ("min_years", "max_years"):
            raw = experience.get(key)
            if isinstance(raw, Decimal):
                raw = float(raw)
            if isinstance(raw, (int, float)) and raw >= 0:
                return float(raw)
    return 0.0


def _normalize_skill_item(
    item: object,
    *,
    default_years: float,
    mode: Literal["objects", "strings"],
) -> dict | str | None:
    skill = None
    years: float | None = None
    if isinstance(item, str):
        skill = item.strip()
    elif isinstance(item, dict):
        raw_skill = item.get("skill") or item.get("name")
        if isinstance(raw_skill, str):
            skill = raw_skill.strip()
        raw_years = item.get("required_years", item.get("years"))
        if isinstance(raw_years, Decimal):
            raw_years = float(raw_years)
        if isinstance(raw_years, (int, float)) and raw_years >= 0:
            years = float(raw_years)
    if not skill:
        return None
    if mode == "strings":
        return skill
    return {"skill": skill, "required_years": years if years is not None else default_years}


def _jd_for_match(parsed_jd: dict, *, mode: Literal["objects", "strings"]) -> dict:
    jd = _json_safe(parsed_jd)
    if not isinstance(jd, dict):
        return {}
    skills = jd.get("skills")
    if not isinstance(skills, dict):
        return jd
    default_years = _default_skill_years(jd)
    normalized = {}
    for key in ("must_have", "good_to_have"):
        items = skills.get(key)
        if not isinstance(items, list):
            normalized[key] = []
            continue
        bucket = []
        for item in items:
            converted = _normalize_skill_item(
                item, default_years=default_years, mode=mode
            )
            if converted is not None:
                bucket.append(converted)
        normalized[key] = bucket
    jd["skills"] = normalized
    return jd


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
        "parsed_resume": _json_safe(parsed_resume),
    }
    skill_modes: tuple[Literal["objects", "strings"], ...] = ("objects", "strings")
    last_error = "422 Unprocessable Entity"
    try:
        with httpx.Client(timeout=120.0) as client:
            for index, mode in enumerate(skill_modes):
                payload = {**base, "parsed_jd": _jd_for_match(parsed_jd, mode=mode)}
                response = client.post(_ai_url("match/resume-jd"), json=payload)
                if response.status_code == 422 and index == 0:
                    last_error = f"422 {(response.text or '').strip()[:2000]}"
                    continue
                try:
                    response.raise_for_status()
                except httpx.HTTPError as exc:
                    raise ValueError(
                        f"Job-fit service unavailable: {_http_error_detail(exc)}"
                    ) from exc
                data = response.json()
                if not isinstance(data, dict):
                    raise ValueError("Invalid response from job-fit service")
                return data
    except httpx.HTTPError as exc:
        raise ValueError(f"Job-fit service unavailable: {_http_error_detail(exc)}") from exc

    raise ValueError(f"Job-fit service unavailable: {last_error}")
