"""Job-fit calculation orchestration for applications."""

from __future__ import annotations

import logging
from decimal import Decimal

from sqlalchemy.orm import Session

from src.models.application import Application
from src.models.job_description import JobDescription
from src.schemas.application import JobFitRunResponse
from src.services.application_ai_service import call_match_resume_jd

logger = logging.getLogger(__name__)

__all__ = [
    "apply_job_fit",
    "rerun_job_fit",
]


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

    score = fit.get("resume_score")
    if not isinstance(score, (int, float)):
        score = fit.get("match_score")
    if isinstance(score, (int, float)):
        application.resume_score = Decimal(str(score))

    yoe = fit.get("candidate_yoe")
    if isinstance(yoe, (int, float)):
        application.candidate_yoe = float(yoe)

    analysis = fit.get("job_fit_analysis")
    if isinstance(analysis, dict):
        application.job_fit_analysis = analysis

    db.add(application)
    logger.info(
        "Job-fit success for application %s: score=%s, yoe=%s",
        application.id,
        application.resume_score,
        application.candidate_yoe,
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
