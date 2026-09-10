#!/usr/bin/env python3
"""Rewrite existing candidate emails to local+<application_id>@domain.

Uses the original address from ``applications.parsed_resume.personal_info.email``
when available; otherwise tags the current mailbox local-part. Candidates with
several applications use their earliest one; candidates with none fall back to
their user id.

Only candidates are touched — org admin, HR, and super admin logins are left alone.

Requires SCREENING_INVITE_OVERRIDE_EMAIL to be set (feature flag for staging mask).

Usage (inside the core-api container):

    docker exec ezscreen-core-api python -m src.maintenance.mask_candidate_emails --dry-run
    docker exec ezscreen-core-api python -m src.maintenance.mask_candidate_emails --apply
"""

from __future__ import annotations

import argparse
import sys
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.session import SessionLocal
from src.models.application import Application
from src.models.enums import UserRole
from src.models.user import User
from src.services.candidate_email_masking import (
    mask_email_for_application,
    masking_enabled,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Mask stored candidate emails as local+<application_id>@domain.",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the rewrites without touching the database.",
    )
    group.add_argument(
        "--apply",
        action="store_true",
        help="Commit the rewrites.",
    )
    return parser.parse_args()


def _earliest_application_by_candidate(db: Session) -> dict[UUID, Application]:
    """Pick one application per candidate so reruns stay deterministic."""
    rows = db.scalars(
        select(Application).order_by(
            Application.applied_at.asc(),
            Application.id.asc(),
        )
    ).all()
    by_candidate: dict[UUID, Application] = {}
    for application in rows:
        by_candidate.setdefault(application.candidate_id, application)
    return by_candidate


def _original_email_from_application(application: Application | None) -> str | None:
    if application is None:
        return None
    parsed = application.parsed_resume
    if not isinstance(parsed, dict):
        return None
    personal = parsed.get("personal_info")
    if not isinstance(personal, dict):
        return None
    value = personal.get("email")
    if isinstance(value, str) and "@" in value.strip():
        return value.strip().lower()
    return None


def main() -> int:
    args = parse_args()

    if not masking_enabled():
        print(
            "SCREENING_INVITE_OVERRIDE_EMAIL is not set — nothing to mask.",
            file=sys.stderr,
        )
        return 1
    print("Masking as local+<application_id>@domain from resume emails")

    db = SessionLocal()
    try:
        candidates = list(
            db.scalars(select(User).where(User.role == UserRole.candidate))
        )
        if not candidates:
            print("No candidate users found.")
            return 0

        app_by_candidate = _earliest_application_by_candidate(db)

        changed = 0
        unchanged = 0
        skipped = 0
        for candidate in candidates:
            application = app_by_candidate.get(candidate.id)
            tag = application.id if application is not None else candidate.id
            original = _original_email_from_application(application) or candidate.email
            masked = mask_email_for_application(original, tag)
            if masked is None:
                skipped += 1
                continue
            if candidate.email == masked:
                unchanged += 1
                continue
            print(f"  {candidate.email}  ->  {masked}")
            candidate.email = masked
            changed += 1

        if args.dry_run:
            db.rollback()
            print(
                f"\nDry run: {changed} would change, "
                f"{unchanged} already masked, {skipped} skipped."
            )
            return 0

        db.commit()
        print(
            f"\nApplied: {changed} updated, "
            f"{unchanged} unchanged, {skipped} skipped."
        )
        return 0
    except Exception as exc:  # noqa: BLE001 - surface the failure to the operator
        db.rollback()
        print(f"Failed: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
