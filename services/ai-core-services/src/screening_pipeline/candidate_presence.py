"""Which interview sessions have a participant (the candidate) in the meeting.

Attendee reports participants already in the call the moment the bot joins,
often before the interview runtime for that session exists, so joins are
remembered here and read when the runtime starts.
"""

from __future__ import annotations

_present_sessions: set[str] = set()


def mark_candidate_joined(session_id: str) -> None:
    _present_sessions.add(str(session_id))


def is_candidate_present(session_id: str) -> bool:
    return str(session_id) in _present_sessions


def forget_session(session_id: str) -> None:
    _present_sessions.discard(str(session_id))
