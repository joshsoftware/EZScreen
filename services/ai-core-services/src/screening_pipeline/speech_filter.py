"""Pure helpers for filtering STT noise / Whisper hallucinations."""

from __future__ import annotations

import re

# Common Whisper hallucinations from silence / background noise
WHISPER_HALLUCINATIONS = frozenset({
    "thank you",
    "thanks",
    "you",
    "yeah",
    "thank you for watching",
    "thanks for watching",
    "subscribe",
})


def is_probable_hallucination(transcript: str, *, min_length: int = 2) -> bool:
    """Return True if transcript looks like noise or a known Whisper hallucination."""
    cleaned = transcript.strip().lower()
    cleaned = re.sub(r"[^\w\s]", "", cleaned)
    return cleaned in WHISPER_HALLUCINATIONS or len(cleaned) < min_length


# A transcript ending on one of these is a sentence the candidate hasn't
# finished ("...the third point is", "...and", "uh").
_CONTINUATION_WORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "so", "because", "since", "if",
    "then", "also", "like", "is", "are", "was", "were", "be", "of", "to",
    "for", "with", "in", "on", "at", "by", "from", "that", "which", "where",
    "when", "while", "as", "than", "first", "second", "third", "next",
    "point", "example", "means", "uh", "um", "uhh", "umm", "er", "ah",
})


def looks_unfinished(transcript: str) -> bool:
    """True if the answer so far stops mid-sentence."""
    text = transcript.strip()
    if not text:
        return False
    if text.endswith((",", "...", "…", "-")):
        return True
    words = re.findall(r"[a-z']+", text.lower())
    return bool(words) and words[-1] in _CONTINUATION_WORDS
