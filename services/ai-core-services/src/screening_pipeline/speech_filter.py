"""Pure helpers for filtering STT noise / Whisper hallucinations."""

from __future__ import annotations

import re

# Common Whisper hallucinations from silence / background noise / brief fillers.
# Keep entries lowercase without punctuation (matched after strip + punct removal).
WHISPER_HALLUCINATIONS = frozenset({
    "thank you",
    "thanks",
    "you",
    "yeah",
    "yes",
    "yep",
    "yup",
    "ok",
    "okay",
    "okie",
    "hmm",
    "hm",
    "mm",
    "mmm",
    "um",
    "uh",
    "uh huh",
    "mhm",
    "mhmm",
    "ah",
    "oh",
    "huh",
    "thank you for watching",
    "thanks for watching",
    "subscribe",
})


def is_probable_hallucination(transcript: str, *, min_length: int = 2) -> bool:
    """Return True if transcript looks like noise or a known Whisper hallucination."""
    cleaned = transcript.strip().lower()
    cleaned = re.sub(r"[^\w\s]", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned in WHISPER_HALLUCINATIONS or len(cleaned) < min_length
