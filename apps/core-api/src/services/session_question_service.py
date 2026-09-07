"""Generate candidate-specific screening questions (JD + resume fit) via AI core."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import httpx

from src.config.settings import settings
from src.models.application import Application
from src.models.job_description import JobDescription

__all__ = [
    "generate_candidate_screening_questions",
]


def _questions_service_url(path: str) -> str:
    base = settings.parsing_service_base_url.rstrip("/")
    return f"{base}/screening/questions{path}"


def _require_parsed_jd(job: JobDescription) -> dict[str, Any]:
    parsed_jd = job.parsed_jd
    if not isinstance(parsed_jd, dict) or not parsed_jd:
        raise ValueError(
            "Job is missing parsed JD data required for screening question generation"
        )
    return parsed_jd


def _require_job_fit(application: Application) -> dict[str, Any]:
    analysis = application.job_fit_analysis
    if not isinstance(analysis, dict) or not analysis:
        raise ValueError(
            "Candidate job-fit analysis is required before generating screening questions"
        )
    return analysis


def generate_candidate_screening_questions(
    *,
    interview_session_id: UUID | str,
    job: JobDescription,
    application: Application,
) -> list[dict[str, Any]]:
    """Call AI core with JD + job-fit (+ resume) and return a questions list for the session."""
    parsed_jd = _require_parsed_jd(job)
    job_fit_analysis = _require_job_fit(application)
    parsed_resume = (
        application.parsed_resume
        if isinstance(application.parsed_resume, dict)
        else None
    )

    body: dict[str, Any] = {
        "interview_session_id": str(interview_session_id),
        "parsed_jd": parsed_jd,
        "job_fit_analysis": job_fit_analysis,
    }
    if parsed_resume:
        body["parsed_resume"] = parsed_resume

    url = _questions_service_url("/generate")
    try:
        with httpx.Client(timeout=180.0) as client:
            response = client.post(url, json=body)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ValueError(
            f"Screening question generation unavailable: {exc}"
        ) from exc

    data = response.json()
    if not isinstance(data, dict):
        raise ValueError("Invalid response from question generation service")

    if data.get("status") != "success":
        raise ValueError(
            data.get("error_message")
            or "Screening question generation did not succeed"
        )

    raw_questions = data.get("questions") or []
    if not isinstance(raw_questions, list) or not raw_questions:
        raise ValueError("Question generation returned no questions")

    questions: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_questions, start=1):
        if isinstance(raw, dict):
            item = dict(raw)
            item.setdefault("id", index)
            questions.append(item)
        else:
            questions.append({"id": index, "question": str(raw)})

    return questions
