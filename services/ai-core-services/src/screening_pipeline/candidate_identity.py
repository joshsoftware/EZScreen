"""Is a meeting participant the candidate? (pure helpers, no I/O)

Attendee reports a joiner's display name and whether they host the meeting,
but not their email, so the candidate is recognised by name: the interview
starts for them, not for HR, an observer or a note-taker bot.
"""

from __future__ import annotations

import re
import unicodedata

# Whole words in a participant's name that mark a bot (note-takers,
# recorders, other AI assistants).
_BOT_WORDS = {
    "bot",
    "notetaker",
    "notetakers",
    "otter",
    "fireflies",
    "fathom",
    "tldv",
    "meetgeek",
    "recorder",
    "recording",
    "transcriber",
    "assistant",
    "ezscreener",
}
_BOT_PHRASES = ("read ai", "note taker", "ai notes", "ai notetaker", "tl dv")


def _words(text: str | None) -> list[str]:
    normalized = unicodedata.normalize("NFKD", str(text or ""))
    ascii_text = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.findall(r"[a-z0-9]+", ascii_text.lower())


def looks_like_bot(participant_name: str | None) -> bool:
    words = _words(participant_name)
    if any(word in _BOT_WORDS for word in words):
        return True
    joined = " ".join(words)
    return any(phrase in joined for phrase in _BOT_PHRASES)


def name_matches_candidate(
    participant_name: str | None,
    first_name: str | None,
    last_name: str | None,
) -> bool:
    """True when the display name shares the candidate's first or last name.

    Display names vary ("Pooja S", "Sharma Pooja", "pooja.sharma"), so one
    shared name word is enough. Single letters (initials) never count.
    """
    candidate_words = {w for w in _words(first_name) + _words(last_name) if len(w) >= 2}
    if not candidate_words:
        return False
    return any(word in candidate_words for word in _words(participant_name))
