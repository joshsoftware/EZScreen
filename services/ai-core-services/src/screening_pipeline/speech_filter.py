"""Pure helpers for filtering STT noise / Whisper hallucinations."""

from __future__ import annotations

import re

# Common Whisper hallucinations from silence / background noise
WHISPER_HALLUCINATIONS = frozenset({
    "thank you",
    "thanks",
    "you",
    "okay",
    "ok",
    "yeah",
    "thank you for watching",
    "thanks for watching",
    "subscribe",
    "no i dont know",
    "okay i dont know",
    "i dont know",
})


def is_probable_hallucination(transcript: str, *, min_length: int = 2) -> bool:
    """Return True if transcript looks like noise or a known Whisper hallucination."""
    cleaned = transcript.strip().lower()
    cleaned = re.sub(r"[^\w\s]", "", cleaned)
    return cleaned in WHISPER_HALLUCINATIONS or len(cleaned) < min_length
