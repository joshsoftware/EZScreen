"""Bots whose interview has ended in this process.

Attendee reconnects the audio stream as the bot leaves. The new connection
starts a fresh runtime with an empty memory; the session's status in the
database still read "in_progress" (the ending runtime writes "completed" only
after its summary), so that runtime started, received the bot's "ended"
webhook and saved "no answers were scored" over the real result (Bugs 44-46).

An interview is marked here the moment it starts ending, before any slow
work, so a runtime started for the same bot afterwards stays idle. Keyed by
bot id: a rescheduled session gets a new bot and starts normally.
"""

from __future__ import annotations

_finished_bots: set[str] = set()


def mark_interview_finished(bot_id: str | None) -> None:
    if bot_id:
        _finished_bots.add(bot_id)


def interview_finished(bot_id: str | None) -> bool:
    return bool(bot_id) and bot_id in _finished_bots
