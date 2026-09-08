"""Deterministic expected-keyword matching for screening answers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Sequence

__all__ = ["KeywordCoverage", "calculate_keyword_coverage"]

_FUZZY_MATCH_THRESHOLD = 0.91
_ABBREVIATED_MATCH_THRESHOLD = 0.75


@dataclass(frozen=True)
class KeywordCoverage:
    """The deterministic keyword coverage of one candidate answer."""

    found: list[str]
    missing: list[str]
    coverage_percent: int

    @property
    def score(self) -> float:
        """Return the keyword component on the 0-10 evaluation scale."""
        return self.coverage_percent / 10


def _coerce_keywords(expected_keywords: Sequence[str] | str) -> list[str]:
    raw_keywords = expected_keywords.split(",") if isinstance(expected_keywords, str) else expected_keywords
    unique_keywords: list[str] = []
    seen: set[str] = set()

    for keyword in raw_keywords:
        cleaned = str(keyword).strip()
        normalized = cleaned.casefold()
        if cleaned and normalized not in seen:
            unique_keywords.append(cleaned)
            seen.add(normalized)

    return unique_keywords


def _tokenize(value: str) -> list[str]:
    """Split prose, punctuation, and camel-case identifiers into word tokens."""
    split_camel_case = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", value)
    split_camel_case = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", split_camel_case)
    return re.findall(r"[a-z0-9]+", split_camel_case.casefold())


def _has_high_confidence_fuzzy_match(transcript: str, keyword_parts: list[str]) -> bool:
    """Recognize likely STT substitutions without accepting distant matches."""
    if sum(len(part) for part in keyword_parts) < 6:
        return False

    transcript_parts = _tokenize(transcript)
    window_size = len(keyword_parts)
    expected_phrase = " ".join(keyword_parts)
    for index in range(len(transcript_parts) - window_size + 1):
        candidate_phrase = " ".join(transcript_parts[index:index + window_size])
        similarity = SequenceMatcher(None, expected_phrase, candidate_phrase).ratio()
        if similarity >= _FUZZY_MATCH_THRESHOLD:
            return True
    return False


def _matched_compound_characters(
    candidate_parts: list[str],
    keyword_parts: list[str],
) -> int:
    """Return matched characters when spoken compound-name parts stay ordered."""
    next_search_start = 0
    matched_characters = 0

    for candidate_part in candidate_parts:
        match_found = False
        for start in range(next_search_start, len(keyword_parts)):
            combined_part = ""
            for end in range(start, len(keyword_parts)):
                combined_part += keyword_parts[end]
                if combined_part == candidate_part:
                    matched_characters += len(combined_part)
                    next_search_start = end + 1
                    match_found = True
                    break
                if len(combined_part) > len(candidate_part):
                    break
            if match_found:
                break
        if not match_found:
            return 0

    return matched_characters


def _has_high_confidence_abbreviated_match(transcript: str, keyword_parts: list[str]) -> bool:
    """Match shortened compound identifiers such as ``copyon arraylist``."""
    keyword_characters = sum(len(part) for part in keyword_parts)
    if len(keyword_parts) < 3 or keyword_characters < 10:
        return False

    transcript_parts = _tokenize(transcript)
    for start in range(len(transcript_parts)):
        for end in range(start + 1, min(len(transcript_parts), start + len(keyword_parts)) + 1):
            candidate_parts = transcript_parts[start:end]
            matched_characters = _matched_compound_characters(candidate_parts, keyword_parts)
            if matched_characters / keyword_characters >= _ABBREVIATED_MATCH_THRESHOLD:
                return True
    return False


def _is_keyword_present(transcript: str, keyword: str) -> bool:
    """Match a keyword directly or as a high-confidence STT variation."""
    lowered_transcript = transcript.casefold()
    parts = _tokenize(keyword)

    # Short language names such as C, C#, and C++ need literal matching to
    # avoid counting unrelated words that merely contain the letter "c".
    if sum(len(part) for part in parts) <= 1:
        pattern = rf"(?<![a-z0-9]){re.escape(keyword.casefold())}(?![a-z0-9])"
        return bool(re.search(pattern, lowered_transcript))

    if not parts:
        return False

    phrase_pattern = r"[^a-z0-9]+".join(re.escape(part) for part in parts)
    pattern = rf"(?<![a-z0-9]){phrase_pattern}(?![a-z0-9])"
    if re.search(pattern, lowered_transcript):
        return True

    return (
        _has_high_confidence_fuzzy_match(transcript, parts)
        or _has_high_confidence_abbreviated_match(transcript, parts)
    )


def calculate_keyword_coverage(
    transcript: str,
    expected_keywords: Sequence[str] | str,
) -> KeywordCoverage:
    """Return deterministic coverage for the supplied expected keywords."""
    keywords = _coerce_keywords(expected_keywords)
    found = [keyword for keyword in keywords if _is_keyword_present(transcript, keyword)]
    missing = [keyword for keyword in keywords if keyword not in found]

    coverage_percent = round((len(found) / len(keywords)) * 100) if keywords else 100
    return KeywordCoverage(
        found=found,
        missing=missing,
        coverage_percent=coverage_percent,
    )
