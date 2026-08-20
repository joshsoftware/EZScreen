"""Job-fit calculation orchestration for applications."""

from __future__ import annotations

import logging
from decimal import Decimal

from sqlalchemy.orm import Session

from src.models.application import Application
from src.models.enums import ApplicationStatus
from src.models.job_description import JobDescription
from src.schemas.application import JobFitRunResponse
from src.services.application_ai_service import call_match_resume_jd

logger = logging.getLogger(__name__)

__all__ = [
    "apply_job_fit",
    "rerun_job_fit",
]


def _coerce_score(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _extract_resume_score(fit: dict) -> float | None:
    """Read resume/match score from AI response (top-level or nested analysis)."""
    for key in ("resume_score", "match_score"):
        score = _coerce_score(fit.get(key))
        if score is not None:
            return score

    analysis = fit.get("job_fit_analysis")
    if isinstance(analysis, dict):
        for key in ("match_score", "resume_score"):
            score = _coerce_score(analysis.get(key))
            if score is not None:
                return score

    return None


def apply_job_fit(
    db: Session,
    job: JobDescription,
    application: Application,
    parsed_resume: dict,
) -> None:
    parsed_jd = job.parsed_jd
    if not parsed_jd:
        logger.warning(
            "Job %s has no parsed_jd; skipping job-fit for application %s",
            job.id,
            application.id,
        )
        return

    try:
        fit = call_match_resume_jd(
            application_id=application.id,
            job_id=job.id,
            parsed_jd=parsed_jd,
            parsed_resume=parsed_resume,
        )
    except Exception:
        logger.exception(
            "Job-fit failed for application %s; application kept without score",
            application.id,
        )
        return

    if fit.get("status") != "success":
        logger.warning(
            "Job-fit returned non-success for application %s: %s",
            application.id,
            fit.get("error_message") or fit,
        )
        return

    score = _extract_resume_score(fit)
    if score is not None:
        application.resume_score = Decimal(str(score))

    yoe = fit.get("candidate_yoe")
    if isinstance(yoe, (int, float)):
        application.candidate_yoe = float(yoe)

    analysis = fit.get("job_fit_analysis")
    if isinstance(analysis, dict):
        application.job_fit_analysis = analysis
    elif fit.get("status") == "success":
        # Some AI deployments return the analysis payload at the top level.
        flat_analysis = {
            key: value
            for key, value in fit.items()
            if key not in {"status", "error_message", "candidate_yoe"}
        }
        if flat_analysis:
            application.job_fit_analysis = flat_analysis

    if application.status == ApplicationStatus.applied:
        application.status = ApplicationStatus.scored

    db.add(application)
    logger.info(
        "Job-fit success for application %s: score=%s, yoe=%s, status=%s",
        application.id,
        application.resume_score,
        application.candidate_yoe,
        application.status.value,
    )


def rerun_job_fit(
    db: Session,
    *,
    application: Application,
) -> JobFitRunResponse:
    job = application.job_description
    if job is None:
        job = db.get(JobDescription, application.job_description_id)
    if job is None:
        raise LookupError("Job not found")
    if not isinstance(application.parsed_resume, dict):
        raise ValueError("Application has no parsed_resume to match")

    apply_job_fit(db, job, application, application.parsed_resume)
    db.commit()
    db.refresh(application)
    return JobFitRunResponse(
        application_id=application.id,
        status="completed",
        resume_score=application.resume_score,
    )
