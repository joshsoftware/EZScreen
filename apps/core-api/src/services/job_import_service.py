"""Import a JD file and map it onto Create Job form fields."""

from __future__ import annotations

import os
import re

from src.schemas.job import JdFormPrefill, JdImportResponse, JdNeedsReviewItem
from src.services.application_ai_service import call_jd_form_prefill

__all__ = ["import_jd_file"]

_MAX_BYTES = 10 * 1024 * 1024
_ALLOWED_EXT = {".pdf", ".txt", ".md", ".docx"}

_JOB_TYPE_ALIASES = {
    "full_time": "full_time",
    "full-time": "full_time",
    "full time": "full_time",
    "fulltime": "full_time",
    "part_time": "part_time",
    "part-time": "part_time",
    "part time": "part_time",
    "parttime": "part_time",
    "contract": "contract",
    "contractor": "contract",
}

_WORK_TYPE_ALIASES = {
    "onsite": "onsite",
    "on-site": "onsite",
    "on site": "onsite",
    "hybrid": "hybrid",
    "remote": "remote",
    "wfh": "remote",
    "work from home": "remote",
}


def _join_lines(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    if isinstance(value, list):
        lines = [str(item).strip() for item in value if str(item).strip()]
        return "\n".join(lines) if lines else None
    return None


def _normalize_enum(value: object, aliases: dict[str, str]) -> str | None:
    if value is None:
        return None
    key = re.sub(r"\s+", " ", str(value).strip().lower())
    return aliases.get(key)


def _normalize_years(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        years = float(value)
    except (TypeError, ValueError):
        return None
    if years < 0 or years > 50:
        return None
    if abs(years * 10 - round(years * 10)) > 1e-6:
        years = round(years, 1)
    return round(years * 10) / 10


def _normalize_needs_review(value: object) -> list[JdNeedsReviewItem]:
    if not isinstance(value, list):
        return []
    items: list[JdNeedsReviewItem] = []
    for raw in value:
        if isinstance(raw, str):
            text = raw.strip()
            if text:
                items.append(JdNeedsReviewItem(label="Other", content=text))
            continue
        if not isinstance(raw, dict):
            continue
        label = str(raw.get("label") or "Other").strip() or "Other"
        content = str(raw.get("content") or "").strip()
        if content:
            items.append(JdNeedsReviewItem(label=label, content=content))
    return items


def _to_form(raw: dict) -> JdFormPrefill:
    return JdFormPrefill(
        title=(str(raw["title"]).strip() if raw.get("title") else None) or None,
        location=(str(raw["location"]).strip() if raw.get("location") else None) or None,
        job_type=_normalize_enum(raw.get("job_type"), _JOB_TYPE_ALIASES),
        work_type=_normalize_enum(raw.get("work_type"), _WORK_TYPE_ALIASES),
        experience_min=_normalize_years(raw.get("experience_min")),
        experience_max=_normalize_years(raw.get("experience_max")),
        role_summary=_join_lines(raw.get("role_summary")),
        about_company=_join_lines(raw.get("about_company")),
        responsibilities=_join_lines(raw.get("responsibilities")),
        must_have_skills_text=_join_lines(raw.get("must_have_skills_text")),
        good_to_have_skills_text=_join_lines(raw.get("good_to_have_skills_text")),
        qualifications=_join_lines(raw.get("qualifications")),
        domain_experience=_join_lines(raw.get("domain_experience")),
        tools_stack=_join_lines(raw.get("tools_stack")),
        needs_review=_normalize_needs_review(raw.get("needs_review")),
    )


def import_jd_file(
    *,
    file_name: str,
    content: bytes,
    content_type: str | None,
) -> JdImportResponse:
    if not content:
        raise ValueError("Uploaded file is empty")
    if len(content) > _MAX_BYTES:
        raise ValueError("JD file must be 10 MB or smaller")

    ext = os.path.splitext(file_name or "")[1].lower()
    if ext not in _ALLOWED_EXT:
        raise ValueError("Unsupported file type. Upload PDF, DOCX, or TXT.")

    data = call_jd_form_prefill(
        file_name=file_name or f"jd{ext}",
        content=content,
        content_type=content_type,
    )
    if data.get("status") != "success":
        raise ValueError(data.get("error_message") or "JD import did not succeed")
    form_raw = data.get("form")
    if not isinstance(form_raw, dict):
        raise ValueError("JD import response missing form data")
    return JdImportResponse(form=_to_form(form_raw))
