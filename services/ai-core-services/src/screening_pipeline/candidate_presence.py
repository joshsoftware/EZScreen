"""Who is in each interview's meeting, and whether the candidate is.

Attendee reports participants already in the call the moment the bot joins,
often before the interview runtime for that session exists, so joins are
remembered here and read when the runtime starts.
"""

from __future__ import annotations

import time
from typing import Any, Dict

from src.core.config import settings
from src.screening_pipeline.candidate_identity import looks_like_bot, name_matches_candidate


def _require_real_candidate() -> bool:
    return bool(getattr(settings, "screening_require_real_candidate", True))


def camera_required() -> bool:
    return bool(getattr(settings, "screening_require_camera_on", True))

# Sessions where the candidate (recognised by name) is in the meeting.
_present_sessions: set[str] = set()
# session id -> participant uuid -> {"name", "is_host", "is_bot", "is_candidate"}
_participants: Dict[str, Dict[str, dict]] = {}
# session id -> participant uuid -> when their last webcam frame arrived
_webcam_seen_at: Dict[str, Dict[str, float]] = {}


def _camera_fresh_seconds() -> float:
    from src.screening_pipeline.prompts import CAMERA_FRAME_FRESH_SECONDS

    return CAMERA_FRAME_FRESH_SECONDS


def record_webcam_frame(session_id: str, participant_uuid: str, now: float | None = None) -> bool:
    """A webcam frame arrived from this participant. True when their camera
    has just come on (no fresh frame from them before)."""
    now = time.monotonic() if now is None else now
    seen = _webcam_seen_at.setdefault(str(session_id), {})
    previous = seen.get(str(participant_uuid))
    seen[str(participant_uuid)] = now
    return previous is None or now - previous > _camera_fresh_seconds()


def _camera_on(session_id: str, participant_uuid: str, now: float) -> bool:
    seen_at = _webcam_seen_at.get(str(session_id), {}).get(str(participant_uuid))
    return seen_at is not None and now - seen_at <= _camera_fresh_seconds()


def candidate_camera_on(session_id: str, now: float | None = None) -> bool:
    """Is the candidate's camera on? Always True when the check is off.

    The candidate is the participant recognised by name; failing that, the
    only non-host person in the meeting (a candidate with a nickname).
    Someone else's camera (HR, an observer) doesn't count.
    """
    if not camera_required():
        return True
    now = time.monotonic() if now is None else now
    people = _participants.get(str(session_id)) or {}
    for uuid, person in people.items():
        if person["is_candidate"] and _camera_on(session_id, uuid, now):
            return True
    others = [uuid for uuid, p in people.items() if not p["is_host"] and not p["is_bot"]]
    return len(others) == 1 and _camera_on(session_id, others[0], now)


def mark_candidate_joined(session_id: str) -> None:
    _present_sessions.add(str(session_id))


def is_candidate_present(session_id: str) -> bool:
    return str(session_id) in _present_sessions


def record_participant(
    session_id: str,
    participant_uuid: str,
    *,
    name: str,
    is_host: bool,
    is_bot: bool,
    is_candidate: bool,
) -> None:
    _participants.setdefault(str(session_id), {})[str(participant_uuid)] = {
        "name": name,
        "is_host": is_host,
        "is_bot": is_bot,
        "is_candidate": is_candidate,
    }
    if is_candidate:
        mark_candidate_joined(session_id)


def remove_participant(session_id: str, participant_uuid: str | None) -> None:
    people = _participants.get(str(session_id))
    if not people or participant_uuid is None:
        return
    _webcam_seen_at.get(str(session_id), {}).pop(str(participant_uuid), None)
    left = people.pop(str(participant_uuid), None)
    if left and left["is_candidate"] and not any(p["is_candidate"] for p in people.values()):
        _present_sessions.discard(str(session_id))


def apply_participant_event(
    session_id: str,
    event: Dict[str, Any],
    candidate_first_name: str | None,
    candidate_last_name: str | None,
) -> bool:
    """Update who is in the meeting from one Attendee participant event (from
    the webhook or the participant_events API). True when it is the candidate
    joining."""
    event_type = str(event.get("event_type") or event.get("event") or "").lower()
    participant_uuid = event.get("participant_uuid")
    if event_type in {"leave", "left", "participant_left", "participant_leave"}:
        remove_participant(session_id, participant_uuid)
        return False
    if event_type not in {"join", "joined", "participant_join", "participant_joined"}:
        return False
    name = str(event.get("participant_name") or "")
    is_host = event.get("participant_is_host") is True
    is_bot = looks_like_bot(name)
    if _require_real_candidate():
        is_candidate = (
            not is_host
            and not is_bot
            and name_matches_candidate(name, candidate_first_name, candidate_last_name)
        )
    else:
        # Feature switched off: anyone joining starts the interview.
        is_candidate = True
    record_participant(
        session_id,
        str(participant_uuid or name),
        name=name,
        is_host=is_host,
        is_bot=is_bot,
        is_candidate=is_candidate,
    )
    return is_candidate


def speech_may_start_interview(session_id: str) -> bool:
    """Someone spoke while the bot waits: may that start the interview?

    Yes if Attendee never reported anyone (its join events were missed, so
    there is nothing to go on), or if exactly one person other than the host
    and bots is there: likely the candidate with a different display name.
    Not when only the host or HR/observers are in the meeting.
    """
    if not _require_real_candidate():
        return True
    people = _participants.get(str(session_id))
    if not people:
        return True
    others = [p for p in people.values() if not p["is_host"] and not p["is_bot"]]
    return len(others) == 1


def forget_session(session_id: str) -> None:
    _present_sessions.discard(str(session_id))
    _participants.pop(str(session_id), None)
    _webcam_seen_at.pop(str(session_id), None)
