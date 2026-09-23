#!/usr/bin/env python3
"""Rewrite existing candidate emails onto the staging invite sink.

Uses the original address from ``applications.parsed_resume.personal_info.email``
when available. Also recovers addresses previously masked as
``local+<application_id>@domain``.

Result shape (dev + SCREENING_INVITE_OVERRIDE_EMAIL)::

    <sink_local>+<candidate_at_domain>.<userid8>@<sink_domain>

Example (SCREENING_INVITE_OVERRIDE_EMAIL=nikhil.gosavi@joshsoftware.com)::

    jane.doe@acme.com
      → nikhil.gosavi+jane.doe_at_acme.com.a1b2c3d4@joshsoftware.com

The short user-id suffix keeps ``users.email`` unique when several old
per-application rows share the same resume mailbox. Meet / invite sending
still rewrites from the resume address to the sink without needing that
suffix (see ``_attendee_emails``).

Only candidates are touched — org admin, HR, and super admin logins are left alone.

Requires APP_ENV=dev and SCREENING_INVITE_OVERRIDE_EMAIL to be set.

Usage (inside the core-api container):

    docker exec ezscreen-core-api python -m src.maintenance.mask_candidate_emails --dry-run
    docker exec ezscreen-core-api python -m src.maintenance.mask_candidate_emails --apply
"""

from __future__ import annotations

import argparse
import re
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
    primary_invite_sink,
)

_UUID_TAG_RE = re.compile(
    r"^[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}$",
    re.IGNORECASE,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Mask stored candidate emails as "
            "<sink>+<candidate_at_domain>.<userid8>@<sink_domain>."
        ),
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


def _email_from_application(application: Application | None) -> str | None:
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


def _recover_original_email(email: str | None) -> str | None:
    """Normalize stored / resume emails back to a candidate identity source.

    - Already on the current sink → strip ``.<userid8>`` suffix if present,
      then return the sink address (mask helper is idempotent on sink form).
    - Old style ``local+<uuid>@domain`` → ``local@domain``.
    - Otherwise return the email unchanged.
    """
    if not isinstance(email, str) or "@" not in email.strip():
        return None
    normalized = email.strip().lower()
    sink = primary_invite_sink()
    if sink:
        sink_local, _, sink_domain = sink.partition("@")
        sink_local = sink_local.split("+", 1)[0]
        if (
            sink_local
            and sink_domain
            and normalized.startswith(f"{sink_local}+")
            and normalized.endswith(f"@{sink_domain}")
        ):
            return normalized

    local, _, domain = normalized.partition("@")
    if "+" not in local or not domain:
        return normalized
    base, tag = local.split("+", 1)
    if base and _UUID_TAG_RE.match(tag):
        return f"{base}@{domain}"
    compact = tag.replace("-", "")
    if base and len(compact) == 32 and re.fullmatch(r"[0-9a-f]+", compact, re.IGNORECASE):
        return f"{base}@{domain}"
    return normalized


def _stored_mask(original: str, candidate_id: UUID) -> str | None:
    """Sink mask plus a short user-id suffix so ``users.email`` stays unique."""
    base = mask_email_for_application(original, candidate_id)
    if base is None:
        return None
    suffix = candidate_id.hex[:8]
    local, _, domain = base.partition("@")
    if local.endswith(f".{suffix}"):
        return base
    # Drop a previous 8-hex uniquifier only (do not strip ``.com`` from tags).
    if "+" in local:
        plus_local, plus_tag = local.split("+", 1)
        if "." in plus_tag:
            core, maybe_id = plus_tag.rsplit(".", 1)
            if re.fullmatch(r"[0-9a-f]{8}", maybe_id, re.IGNORECASE):
                local = f"{plus_local}+{core}"
    return f"{local}.{suffix}@{domain}"


def main() -> int:
    args = parse_args()

    if not masking_enabled():
        print(
            "Masking disabled — set APP_ENV=dev and SCREENING_INVITE_OVERRIDE_EMAIL.",
            file=sys.stderr,
        )
        return 1

    sink = primary_invite_sink()
    print(f"Invite sink: {sink}")
    print("Masking as <sink>+<candidate_at_domain>.<userid8>@<sink_domain>")

    db = SessionLocal()
    try:
        candidates = list(
            db.scalars(
                select(User)
                .where(User.role == UserRole.candidate)
                .order_by(User.created_at.asc(), User.id.asc())
            )
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
            raw = _email_from_application(application) or candidate.email
            original = _recover_original_email(raw)
            if original is None:
                skipped += 1
                continue
            masked = _stored_mask(original, candidate.id)
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
