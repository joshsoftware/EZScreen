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


def compute_final_summary(
    evaluations: List[Dict[str, Any]],
    *,
    recommendation_threshold: float = RECOMMENDATION_THRESHOLD,
) -> Dict[str, Any] | None:
    """Calculate a summary from persisted question evaluations only.

    Topic scores average a follow-up with its main answer. The overall score
    then applies the screening weights (Must-have 60, Domain 20, Good to have
    10, Skill gaps 10). A category that was not asked gives its weight to
    Must-have. The result is out of 100, shown out of 10.
    """
    persisted_evaluations = [item for item in evaluations if isinstance(item, dict)]
    if not persisted_evaluations:
        return None

    # Imported lazily: routing_engine imports _score from this module.
    from src.screening_pipeline.routing_engine import calculate_final_weighted_score

    summary = calculate_final_weighted_score(persisted_evaluations)
    overall_score = summary["overall_score"]
    if overall_score >= recommendation_threshold:
        final_recommendation = "shortlist_for_l1"
    else:
        final_recommendation = "reject"

    return {
        "total_score": summary["total_raw_score"],
        "max_possible_score": 100.0,
        "overall_score": overall_score,
        "final_recommendation": final_recommendation,
    }
