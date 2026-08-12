"""Organization business logic."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.models.application import Application
from src.models.job_description import JobDescription
from src.models.organization import Organization
from src.models.user import User
from src.schemas.organization import OrganizationCreate, OrganizationUpdate

__all__ = [
    "list_organizations",
    "get_organization",
    "create_organization",
    "update_organization",
    "deactivate_organization",
    "organization_stats",
    "organization_counts_map",
]


def organization_counts_map(db: Session) -> dict[UUID, dict[str, int]]:
    user_rows = db.execute(
        select(User.organization_id, func.count(User.id))
        .where(User.organization_id.is_not(None))
        .group_by(User.organization_id)
    ).all()
    job_rows = db.execute(
        select(JobDescription.organization_id, func.count(JobDescription.id)).group_by(
            JobDescription.organization_id
        )
    ).all()
    app_rows = db.execute(
        select(JobDescription.organization_id, func.count(Application.id))
        .join(Application, Application.job_description_id == JobDescription.id)
        .group_by(JobDescription.organization_id)
    ).all()

    stats: dict[UUID, dict[str, int]] = {}
    for org_id, count in user_rows:
        if org_id:
            stats.setdefault(org_id, {})["user_count"] = int(count)
    for org_id, count in job_rows:
        stats.setdefault(org_id, {})["job_count"] = int(count)
    for org_id, count in app_rows:
        stats.setdefault(org_id, {})["application_count"] = int(count)
    return stats


def organization_stats(db: Session, organization_id: UUID) -> dict[str, int]:
    all_stats = organization_counts_map(db)
    return {
        "user_count": all_stats.get(organization_id, {}).get("user_count", 0),
        "job_count": all_stats.get(organization_id, {}).get("job_count", 0),
        "application_count": all_stats.get(organization_id, {}).get(
            "application_count", 0
        ),
    }


def list_organizations(
    db: Session,
    *,
    page: int = 1,
    limit: int = 20,
    q: str | None = None,
    active: bool | None = None,
) -> list[Organization]:
    stmt = select(Organization).order_by(Organization.created_at.desc())
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            (Organization.name.ilike(pattern)) | (Organization.domain.ilike(pattern))
        )
    if active is not None:
        stmt = stmt.where(Organization.is_active.is_(active))
    offset = max(page - 1, 0) * limit
    stmt = stmt.offset(offset).limit(min(limit, 50))
    return list(db.scalars(stmt).all())


def get_organization(db: Session, organization_id: UUID) -> Organization | None:
    return db.get(Organization, organization_id)


def _domain_taken(
    db: Session, domain: str | None, exclude_id: UUID | None = None
) -> bool:
    if not domain:
        return False
    stmt = select(Organization.id).where(Organization.domain == domain)
    if exclude_id:
        stmt = stmt.where(Organization.id != exclude_id)
    return db.scalar(stmt) is not None


def create_organization(db: Session, data: OrganizationCreate) -> Organization:
    if _domain_taken(db, data.domain):
        raise ValueError("Domain already in use")
    org = Organization(
        name=data.name,
        domain=data.domain,
        logo_url=data.logo_url,
        is_active=True,
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def update_organization(
    db: Session, org: Organization, data: OrganizationUpdate
) -> Organization:
    payload = data.model_dump(exclude_unset=True)
    if "domain" in payload and _domain_taken(db, payload["domain"], exclude_id=org.id):
        raise ValueError("Domain already in use")
    for key, value in payload.items():
        setattr(org, key, value)
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def deactivate_organization(db: Session, org: Organization) -> Organization:
    org.is_active = False
    db.add(org)
    db.commit()
    db.refresh(org)
    return org
