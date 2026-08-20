"""HR bulk resume ingest flow."""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.db.session import SessionLocal
from src.models.application import Application
from src.models.enums import ApplicationStatus, JobStatus, UserRole, UserStatus
from src.models.job_description import JobDescription
from src.models.user import User
from src.schemas.application import (
    BulkCreateRequest,
    BulkCreateResponse,
    UploadFileRequest,
    UploadUrlItem,
    UploadUrlsResponse,
)
from src.services import storage_service
from src.services.application_ai_service import call_parse_resume
from src.services.application_job_fit_service import apply_job_fit

logger = logging.getLogger(__name__)

__all__ = [
    "assert_job_accepts_applications",
    "create_upload_urls",
    "enqueue_bulk_resumes",
]


def assert_job_accepts_applications(job: JobDescription) -> None:
    if job.status != JobStatus.published:
        raise ValueError("Job must be published to accept applications")


def create_upload_urls(
    job: JobDescription,
    files: list[UploadFileRequest],
) -> UploadUrlsResponse:
    uploads: list[UploadUrlItem] = []
    for file in files:
        s3_key = storage_service.build_resume_s3_key(
            job.organization_id,
            job.id,
            file.file_name,
        )
        upload_url, expires_at = storage_service.create_presigned_upload_url(
            s3_key,
            file.content_type,
        )
        uploads.append(
            UploadUrlItem(
                file_name=file.file_name,
                s3_key=s3_key,
                upload_url=upload_url,
                expires_at=expires_at,
            )
        )
    return UploadUrlsResponse(uploads=uploads)


def enqueue_bulk_resumes(
    job: JobDescription,
    body: BulkCreateRequest,
) -> BulkCreateResponse:
    assert_job_accepts_applications(job)

    for resume in body.resumes:
        storage_service.validate_resume_s3_key(
            resume.s3_key,
            organization_id=job.organization_id,
            job_id=job.id,
        )

    for resume in body.resumes:
        thread = threading.Thread(
            target=_process_resume,
            args=(job.id, resume.s3_key, resume.file_name),
            daemon=True,
            name=f"resume-{resume.file_name[:40]}",
        )
        thread.start()

    return BulkCreateResponse(job_id=job.id, queued=len(body.resumes))


def _process_resume(job_id: UUID, s3_key: str, file_name: str) -> None:
    db = SessionLocal()
    try:
        job = db.get(JobDescription, job_id)
        if job is None:
            logger.error("Job %s not found while processing %s", job_id, file_name)
            return

        parse_payload = call_parse_resume(s3_key=s3_key, file_name=file_name)
        if parse_payload.get("status") != "success":
            raise ValueError(
                parse_payload.get("error_message") or "Resume parsing did not succeed"
            )

        parsed_resume = parse_payload.get("parsed_resume")
        if not isinstance(parsed_resume, dict):
            raise ValueError("Parse response missing parsed_resume")
        logger.info(
            "Resume parse success for job %s, file %s",
            job_id,
            file_name,
        )

        personal = _personal_info(parsed_resume)
        email = _extract_email(personal)
        if not email:
            raise ValueError("Could not extract candidate email from parsed resume")

        candidate = _find_or_create_candidate(db, email, personal)
        application = _create_application(
            db,
            job=job,
            candidate=candidate,
            s3_key=s3_key,
            parsed_resume=parsed_resume,
        )
        logger.info(
            "Application created for job %s, file %s, candidate %s, application %s",
            job_id,
            file_name,
            candidate.id,
            application.id,
        )
        db.commit()
        db.refresh(application)
        db.refresh(job)

        apply_job_fit(db, job, application, parsed_resume)
        db.commit()
        logger.info(
            "Resume pipeline completed for job %s, file %s, application %s",
            job_id,
            file_name,
            application.id,
        )
    except Exception:
        logger.exception("Failed processing resume %s for job %s", file_name, job_id)
        db.rollback()
    finally:
        db.close()


def _find_or_create_candidate(
    db: Session,
    email: str,
    personal: dict,
) -> User:
    normalized = _normalize_email(email)
    if not normalized:
        raise ValueError("Could not extract candidate email from parsed resume")

    existing = _get_candidate_by_email(db, normalized)
    if existing is not None:
        return _use_existing_candidate(db, existing, personal)

    candidate = User(
        email=normalized,
        role=UserRole.candidate,
        organization_id=None,
        password_hash=None,
        first_name=_string_field(personal, "first_name", max_len=100),
        last_name=_string_field(personal, "last_name", max_len=100),
        phone=_string_field(personal, "phone_number", max_len=50)
        or _string_field(personal, "phone", max_len=50),
        status=UserStatus.active,
    )
    db.add(candidate)
    try:
        with db.begin_nested():
            db.flush()
    except IntegrityError:
        # Another worker created this candidate between our lookup and insert.
        db.expunge(candidate)
        existing = _get_candidate_by_email(db, normalized)
        if existing is None:
            raise ValueError(f"Could not resolve candidate for email {normalized}") from None
        return _use_existing_candidate(db, existing, personal)
    return candidate


def _get_candidate_by_email(db: Session, normalized_email: str) -> User | None:
    return db.scalar(select(User).where(func.lower(User.email) == normalized_email))


def _use_existing_candidate(db: Session, existing: User, personal: dict) -> User:
    if existing.role != UserRole.candidate:
        raise ValueError(f"Email {existing.email} belongs to a non-candidate user")
    _fill_candidate_profile(existing, personal)
    db.add(existing)
    db.flush()
    return existing


def _fill_candidate_profile(user: User, personal: dict) -> None:
    first_name = _string_field(personal, "first_name", max_len=100)
    last_name = _string_field(personal, "last_name", max_len=100)
    phone = _string_field(personal, "phone_number", max_len=50) or _string_field(
        personal, "phone", max_len=50
    )
    if first_name and not user.first_name:
        user.first_name = first_name
    if last_name and not user.last_name:
        user.last_name = last_name
    if phone and not user.phone:
        user.phone = phone


def _create_application(
    db: Session,
    *,
    job: JobDescription,
    candidate: User,
    s3_key: str,
    parsed_resume: dict,
) -> Application:
    now = datetime.now(timezone.utc)
    application = Application(
        job_description_id=job.id,
        candidate_id=candidate.id,
        resume_url=s3_key,
        parsed_resume=parsed_resume,
        candidate_yoe=_extract_yoe(parsed_resume),
        status=ApplicationStatus.applied,
        applied_at=now,
    )
    db.add(application)
    try:
        db.flush()
    except IntegrityError as exc:
        raise ValueError("Candidate has already applied to this job") from exc
    return application


def _personal_info(parsed_resume: dict) -> dict:
    info = parsed_resume.get("personal_info")
    return info if isinstance(info, dict) else {}


def _string_field(data: dict, key: str, *, max_len: int) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text[:max_len]


def _extract_email(personal: dict) -> str:
    value = personal.get("email")
    if isinstance(value, str):
        return _normalize_email(value)
    return ""


def _normalize_email(value: str) -> str:
    normalized = value.strip().lower()
    if "@" not in normalized:
        return ""
    return normalized


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
