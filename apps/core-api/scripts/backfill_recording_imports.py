#!/usr/bin/env python3
"""Schedule meeting-recording copies for interviews that ended before the
recording import existed.

Copies are normally scheduled by ai-core when the bot's meeting ends, so
interviews completed earlier never got one. This queues them; ai-core's
recording poller then copies each MP4 into MinIO. Attendee only keeps
recordings in short-term storage, so run this soon after deploying.

Usage (from apps/core-api, or `docker compose exec core-api ...`):

    python -m scripts.backfill_recording_imports            # dry run
    python -m scripts.backfill_recording_imports --apply
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure apps/core-api is on sys.path when run as a script
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from sqlalchemy import select

from src.db.session import SessionLocal
from src.models.enums import InterviewStatus
from src.models.interview_session import InterviewSession
from src.services import recording_import_service


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Queue recording copies for completed interviews that have none."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually schedule the copies (default is a dry run).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    now = datetime.now(timezone.utc)
    queued = skipped = 0
    with SessionLocal() as db:
        sessions = db.scalars(
            select(InterviewSession)
            .where(InterviewSession.status == InterviewStatus.completed)
            .order_by(InterviewSession.completed_at.asc().nullsfirst())
        ).all()
        for session in sessions:
            meta = session.interview_metadata if isinstance(session.interview_metadata, dict) else {}
            bot_id = meta.get("bot_id")
            if not isinstance(bot_id, str) or not bot_id:
                skipped += 1
                continue
            if recording_import_service.recording_import_state(session):
                skipped += 1
                continue
            print(f"{'queue' if args.apply else 'would queue'} {session.id} (bot {bot_id})")
            if args.apply:
                recording_import_service.schedule_import(
                    db, session, bot_id=bot_id, import_after=now
                )
            queued += 1
    action = "Queued" if args.apply else "Would queue"
    print(f"{action} {queued} recording copies; skipped {skipped} (no bot or already scheduled).")
    if not args.apply and queued:
        print("Run again with --apply to schedule them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
