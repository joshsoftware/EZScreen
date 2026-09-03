"""Generate and store job-level screening question banks via AI core."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from src.config.settings import settings
from src.models.job_description import JobDescription

__all__ = [
    "generate_job_screening_questions",
    "regenerate_job_screening_questions",
    "save_job_screening_questions",
    "screening_questions_payload",
]

_VALID_CATEGORIES = frozenset(
    {"must_have", "must_have_matched", "good_to_have", "experience_domain", "lacking_skill"}
)
_VALID_DEPTHS = frozenset({"aware", "partial_depth", "full_depth"})


def _questions_service_url(path: str) -> str:
    base = settings.parsing_service_base_url.rstrip("/")
    return f"{base}/screening/questions{path}"


def _normalize_parsed_jd(parsed_jd: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(parsed_jd, dict):
        raise ValueError("Job is missing parsed JD data required for question generation")
    return parsed_jd


def screening_questions_payload(
    *,
    status: str,
    questions: list[dict[str, Any]] | None = None,
    error_message: str | None = None,
) -> dict[str, Any]:
    return {
        "status": status,
        "count": len(questions) if questions else 0,
        "questions": questions or [],
        "error_message": error_message,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_job_screening_questions(job: JobDescription) -> dict[str, Any]:
    """Call AI core to build a JD question bank. Returns payload for screening_questions column."""
    parsed_jd = _normalize_parsed_jd(job.parsed_jd)
    url = _questions_service_url("/generate")
    body = {
        "interview_session_id": str(job.id),
        "parsed_jd": parsed_jd,
    }

    try:
        with httpx.Client(timeout=180.0) as client:
            response = client.post(url, json=body)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        return screening_questions_payload(
            status="error",
            error_message=f"Question generation service unavailable: {exc}",
        )

    data = response.json()
    if not isinstance(data, dict):
        return screening_questions_payload(
            status="error",
            error_message="Invalid response from question generation service",
        )

    if data.get("status") != "success":
        return screening_questions_payload(
            status="error",
            error_message=data.get("error_message") or "Question generation did not succeed",
        )

    raw_questions = data.get("questions") or []
    if not isinstance(raw_questions, list):
        return screening_questions_payload(
            status="error",
            error_message="Question generation response missing questions array",
        )

    questions = [q if isinstance(q, dict) else dict(q) for q in raw_questions]
    return screening_questions_payload(status="success", questions=questions)


def regenerate_job_screening_questions(db, job: JobDescription) -> JobDescription:
    job.screening_questions = generate_job_screening_questions(job)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def normalize_screening_questions(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, raw in enumerate(questions, start=1):
        if not isinstance(raw, dict):
            continue
        question_text = str(raw.get("question") or "").strip()
        if not question_text:
            continue
        category = str(raw.get("category") or "must_have").strip()
        if category not in _VALID_CATEGORIES:
            category = "must_have"
        depth = str(raw.get("answer_depth") or "partial_depth").strip()
        if depth not in _VALID_DEPTHS:
            depth = "partial_depth"
        keywords = raw.get("expected_keywords") or []
        if isinstance(keywords, str):
            keywords = [part.strip() for part in keywords.split(",") if part.strip()]
        elif isinstance(keywords, list):
            keywords = [str(item).strip() for item in keywords if str(item).strip()]
        else:
            keywords = []
        normalized.append(
            {
                "id": index,
                "category": category,
                "skill_focus": str(raw.get("skill_focus") or "").strip(),
                "question": question_text,
                "expected_keywords": keywords,
                "answer_depth": depth,
            }
        )
    return normalized


def save_job_screening_questions(
    db,
    job: JobDescription,
    questions: list[dict[str, Any]],
) -> JobDescription:
    normalized = normalize_screening_questions(questions)
    existing = job.screening_questions if isinstance(job.screening_questions, dict) else {}
    now = datetime.now(timezone.utc).isoformat()
    job.screening_questions = {
        "status": "success" if normalized else "draft",
        "count": len(normalized),
        "questions": normalized,
        "error_message": None,
        "generated_at": existing.get("generated_at") or now,
        "updated_at": now,
    }
    db.add(job)
    db.commit()
    db.refresh(job)
    return job
