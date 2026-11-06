"""Pure scoring helpers for interview final summary (no I/O)."""

from __future__ import annotations

from typing import Any, Dict, List

from src.screening_pipeline.prompts import RECOMMENDATION_THRESHOLD


def _score(value: Any) -> float:
    """Convert a persisted score to the supported 0-10 range."""
    try:
        return max(0.0, min(10.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def topic_score(evaluation: Dict[str, Any]) -> float:
    """A question's score with its follow-up: the higher of the two.

    A follow-up is asked only after a weak main answer, about the keywords it
    missed: a second chance. A question scores the better of its main answer
    and its best follow-up, so a failed follow-up never lowers it and a good
    one counts in full (not averaged).
    """
    primary_score = _score(evaluation.get("score"))
    follow_ups = evaluation.get("follow_ups")
    follow_up_scores = [
        _score(fu["score"])
        for fu in follow_ups
        if isinstance(fu, dict) and fu.get("score") is not None
    ] if isinstance(follow_ups, list) else []
    return max([primary_score, *follow_up_scores])


def compute_final_summary(
    evaluations: List[Dict[str, Any]],
    *,
    recommendation_threshold: float = RECOMMENDATION_THRESHOLD,
) -> Dict[str, Any] | None:
    """Calculate a summary from persisted question evaluations only.

    Every persisted evaluation—including a zero-score skip—is one main topic
    worth 10 points. A follow-up is part of that topic, so its score is
    averaged with the main score instead of increasing the maximum score.
    """
    persisted_evaluations = [item for item in evaluations if isinstance(item, dict)]
    persisted_question_count = len(persisted_evaluations)
    if persisted_question_count == 0:
        return None

    total_score = 0.0
    for evaluation in persisted_evaluations:
        total_score += topic_score(evaluation)

    max_possible_score = persisted_question_count * 10
    overall_score = round((total_score / max_possible_score) * 10, 1)

    if overall_score >= recommendation_threshold:
        final_recommendation = "shortlist_for_l1"
    else:
        final_recommendation = "reject"

    return {
        "total_score": round(total_score, 1),
        "max_possible_score": max_possible_score,
        "overall_score": overall_score,
        "final_recommendation": final_recommendation,
    }
