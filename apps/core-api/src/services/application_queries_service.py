"""Application read/query helpers."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from src.models.application import Application
from src.schemas.application import ApplicationDetailResponse, ApplicantListItem

__all__ = [
    "list_applicants",
    "get_application",
    "application_to_detail_response",
]


def list_applicants(
    db: Session,
    *,
    job_id: UUID,
    page: int = 1,
    limit: int = 50,
) -> list[ApplicantListItem]:
    offset = max(page - 1, 0) * limit
    stmt = (
        select(Application)
        .options(selectinload(Application.candidate))
        .where(Application.job_description_id == job_id)
        .order_by(Application.resume_score.desc().nullslast(), Application.created_at.desc())
        .offset(offset)
        .limit(min(limit, 50))
    )
    applications = list(db.scalars(stmt).all())
    return [
        ApplicantListItem(
            id=application.id,
            job_description_id=application.job_description_id,
            candidate_id=application.candidate_id,
            status=application.status.value,
            candidate_yoe=application.candidate_yoe,
            resume_score=application.resume_score,
            first_name=application.candidate.first_name if application.candidate else None,
            last_name=application.candidate.last_name if application.candidate else None,
            email=application.candidate.email if application.candidate else None,
            phone=application.candidate.phone if application.candidate else None,
            created_at=application.created_at,
        )
        for application in applications
    ]


def get_application(db: Session, application_id: UUID) -> Application | None:
    stmt = (
        select(Application)
        .options(
            selectinload(Application.candidate),
            selectinload(Application.job_description),
        )
        .where(Application.id == application_id)
    )
    return db.scalar(stmt)


def application_to_detail_response(
    application: Application,
) -> ApplicationDetailResponse:
    candidate = application.candidate
    return ApplicationDetailResponse(
        id=application.id,
        job_description_id=application.job_description_id,
        candidate_id=application.candidate_id,
        status=application.status.value,
        candidate_yoe=application.candidate_yoe,
        resume_score=application.resume_score,
        first_name=candidate.first_name if candidate else None,
        last_name=candidate.last_name if candidate else None,
        email=candidate.email if candidate else None,
        phone=candidate.phone if candidate else None,
        parsed_resume=application.parsed_resume,
        job_fit_analysis=application.job_fit_analysis,
    )
