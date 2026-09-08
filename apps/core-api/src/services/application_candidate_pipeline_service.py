"""Post-submit pipeline for candidate portal applications."""

from __future__ import annotations

import logging
import threading
from uuid import UUID

from src.db.session import SessionLocal
from src.models.application import Application
from src.models.enums import ApplicationStatus, TimelineActorType, TimelineEventType
from src.models.job_description import JobDescription
from src.services.application_ai_service import call_parse_resume
from src.services.application_job_fit_service import apply_job_fit
from src.services.application_timeline_service import append_timeline_event
from src.services.email_service import (
    ApplicationConfirmationPayload,
    send_application_confirmation,
)
from src.services.storage_service import resume_display_name

logger = logging.getLogger(__name__)

__all__ = [
    "enqueue_candidate_application_pipeline",
]


def enqueue_candidate_application_pipeline(
    *,
    application_id: UUID,
    job_id: UUID,
    s3_key: str,
    candidate_email: str,
    candidate_name: str,
    job_title: str,
    organization_name: str | None = None,
) -> None:
    thread = threading.Thread(
        target=_process_candidate_application,
        args=(
            application_id,
            job_id,
            s3_key,
            candidate_email,
            candidate_name,
            job_title,
            organization_name,
        ),
        daemon=True,
        name=f"candidate-app-{application_id}",
    )
    thread.start()


def _process_candidate_application(
    application_id: UUID,
    job_id: UUID,
    s3_key: str,
    candidate_email: str,
    candidate_name: str,
    job_title: str,
    organization_name: str | None,
) -> None:
    send_application_confirmation(
        ApplicationConfirmationPayload(
            to_email=candidate_email,
            candidate_name=candidate_name,
            job_title=job_title,
            organization_name=organization_name,
        )
    )

    db = SessionLocal()
    try:
        application = db.get(Application, application_id)
        job = db.get(JobDescription, job_id)
        if application is None or job is None:
            logger.error(
                "Application %s or job %s not found for candidate pipeline",
                application_id,
                job_id,
            )
            return

        file_name = resume_display_name(s3_key)
        parse_payload = call_parse_resume(s3_key=s3_key, file_name=file_name)
        if parse_payload.get("status") != "success":
            raise ValueError(
                parse_payload.get("error_message") or "Resume parsing did not succeed"
            )

        parsed_resume = parse_payload.get("parsed_resume")
        if not isinstance(parsed_resume, dict):
            raise ValueError("Parse response missing parsed_resume")

        application.parsed_resume = parsed_resume
        application.candidate_yoe = _extract_yoe(parsed_resume)
        db.add(application)
        append_timeline_event(
            db,
            application=application,
            event_type=TimelineEventType.resume_parsed,
            actor_type=TimelineActorType.system,
            to_status=ApplicationStatus.applied,
        )
        db.commit()
        db.refresh(application)
        db.refresh(job)
        logger.info(
            "Resume parsed for candidate application %s (job %s)",
            application_id,
            job_id,
        )

        apply_job_fit(db, job, application, parsed_resume)
        db.commit()
        logger.info(
            "Candidate application pipeline completed for application %s",
            application_id,
        )
    except Exception:
        logger.exception(
            "Candidate application pipeline failed for application %s",
            application_id,
        )
        db.rollback()
    finally:
        db.close()


def _extract_yoe(parsed_resume: dict) -> float | None:
    experience = parsed_resume.get("experience")
    if isinstance(experience, dict):
        total = experience.get("total_years")
        if isinstance(total, (int, float)):
            return float(total)
    relevant = parsed_resume.get("relevant_experience")
    if isinstance(relevant, dict):
        total = relevant.get("total_years")
        if isinstance(total, (int, float)):
            return float(total)
    return None
