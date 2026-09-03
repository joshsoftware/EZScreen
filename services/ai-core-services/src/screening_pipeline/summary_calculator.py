"""Pure scoring helpers for interview final summary (no I/O)."""

from __future__ import annotations

from typing import Any, Dict, List

from src.screening_pipeline.prompts import RECOMMENDATION_THRESHOLD


def compute_final_summary(
    evaluations: List[Dict[str, Any]],
    *,
    recommendation_threshold: float = RECOMMENDATION_THRESHOLD,
) -> Dict[str, Any] | None:
    """Calculate final_summary from per-question evaluations. Returns None if empty."""
    total_questions = len(evaluations)
    if total_questions == 0:
        return None

    total_score = 0.0
    for ev in evaluations:
        primary_score = ev.get("score", 0)
        follow_ups = ev.get("follow_ups", [])
        if follow_ups and follow_ups[0].get("score") is not None:
            topic_score = (primary_score + follow_ups[0]["score"]) / 2
        else:
            topic_score = primary_score
        total_score += topic_score

    max_possible_score = total_questions * 10
    overall_score = round((total_score / max_possible_score) * 10, 1)

    if overall_score >= recommendation_threshold:
        final_recommendation = "shortlist_for_l1"
    else:
        final_recommendation = "reject"

    return {
        "total_score": total_score,
        "max_possible_score": max_possible_score,
        "overall_score": overall_score,
        "final_recommendation": final_recommendation,
    }
