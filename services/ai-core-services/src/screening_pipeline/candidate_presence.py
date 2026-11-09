"""Who is in each interview's meeting, and whether the candidate is.

Attendee reports participants already in the call the moment the bot joins,
often before the interview runtime for that session exists, so joins are
remembered here and read when the runtime starts.
"""

from __future__ import annotations

from typing import Dict

# Sessions where the candidate (recognised by name) is in the meeting.
_present_sessions: set[str] = set()
# session id -> participant uuid -> {"name", "is_host", "is_bot", "is_candidate"}
_participants: Dict[str, Dict[str, dict]] = {}


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


def remove_participant(session_id: str, participant_uuid: str | None) -> None:
    people = _participants.get(str(session_id))
    if not people or participant_uuid is None:
        return
    left = people.pop(str(participant_uuid), None)
    if left and left["is_candidate"] and not any(p["is_candidate"] for p in people.values()):
        _present_sessions.discard(str(session_id))


def speech_may_start_interview(session_id: str) -> bool:
    """Someone spoke while the bot waits: may that start the interview?

    Yes if Attendee never reported anyone (its join events were missed, so
    there is nothing to go on), or if exactly one person other than the host
    and bots is there: likely the candidate with a different display name.
    Not when only the host or HR/observers are in the meeting.
    """
    people = _participants.get(str(session_id))
    if not people:
        return True
    others = [p for p in people.values() if not p["is_host"] and not p["is_bot"]]
    return len(others) == 1


def forget_session(session_id: str) -> None:
    _present_sessions.discard(str(session_id))
    _participants.pop(str(session_id), None)
