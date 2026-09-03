"""Pure helpers for parsing LLM question-generation output."""

from __future__ import annotations

from typing import Any

from src.common.llm_utils import parse_llm_json
from src.question_generation.schemas import GeneratedQuestion


def parse_questions(raw: Any) -> list[GeneratedQuestion]:
    """Normalize LLM output into a list of GeneratedQuestion models."""
    parsed_questions = parse_llm_json(raw) if isinstance(raw, str) else raw

    if isinstance(parsed_questions, dict):
        for key in ("questions", "generated_questions", "data"):
            if key in parsed_questions and isinstance(parsed_questions[key], list):
                parsed_questions = parsed_questions[key]
                break

    if not isinstance(parsed_questions, list):
        raise ValueError(f"Expected JSON array, got {type(parsed_questions).__name__}")

    return [GeneratedQuestion(**q) for q in parsed_questions]
