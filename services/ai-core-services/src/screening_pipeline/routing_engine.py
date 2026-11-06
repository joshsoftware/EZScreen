"""
Dynamic Routing Engine for AI Screening Pipeline.
Handles chunk-based state transitions, rolling average calculations,
and backward recovery after downgrades.
"""

from typing import Any, Dict, List, Tuple, Optional

from src.screening_pipeline.summary_calculator import topic_score

# ─── Configuration ────────────────────────────────────────────────────────────
CHUNK_SIZE = 3            # Evaluate every N questions per category
DOWNGRADE_THRESHOLD = 3.0  # Rolling average at or below this triggers a downgrade

# Priority order: must-have first, then domain, good-to-have, lacking last
CATEGORIES_ORDER = [
    "must_have_matched",
    "experience_domain",
    "good_to_have",
    "lacking_skill",
]


def calculate_rolling_average(evaluations: List[Dict[str, Any]]) -> float:
    """Calculate the rolling average of evaluated topics."""
    persisted_evaluations = [item for item in evaluations if isinstance(item, dict)]
    persisted_question_count = len(persisted_evaluations)
    if persisted_question_count == 0:
        return 0.0

    total_score = 0.0
    for evaluation in persisted_evaluations:
        total_score += topic_score(evaluation)

    return round(total_score / persisted_question_count, 1)


# Points each category is worth out of 100 (agreed with the team, Nov 2026).
CATEGORY_WEIGHTS = {
    "must_have_matched": 60,
    "experience_domain": 20,
    "good_to_have": 10,
    "lacking_skill": 10,
}


def _planned_counts(planned_questions: Optional[List[Dict[str, Any]]]) -> Optional[Dict[str, int]]:
    """Planned questions per category, or None when the plan is unknown."""
    if not planned_questions:
        return None
    counts = {cat: 0 for cat in CATEGORY_WEIGHTS}
    for question in planned_questions:
        if not isinstance(question, dict):
            continue
        category = question.get("category", "must_have_matched")
        if category in counts:
            counts[category] += 1
    return counts


def calculate_final_weighted_score(
    evaluations: List[Dict[str, Any]],
    planned_questions: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Weighted score: Must-have 60, Domain 20, Good to have 10, Skill gaps 10.

    Every planned question counts: one that was never asked (the screening
    ended early) scores 0, so a category's average is taken over all its
    planned questions. Each category earns (average / 10) x its weight. A
    category the screening had no questions for at all is left out of the
    maximum, since it could not be asked. Without a plan, each category is
    averaged over its answered questions.
    """
    totals = {cat: {"total": 0.0, "count": 0} for cat in CATEGORY_WEIGHTS}

    for evaluation in evaluations:
        category = evaluation.get("category")
        if category not in totals:
            continue

        totals[category]["total"] += topic_score(evaluation)
        totals[category]["count"] += 1

    planned = _planned_counts(planned_questions)
    question_counts = {
        cat: {
            "answered": data["count"],
            # Never fewer than answered (a plan may be incomplete).
            "planned": max(planned[cat], data["count"]) if planned else data["count"],
        }
        for cat, data in totals.items()
    }
    asked = [cat for cat in CATEGORY_WEIGHTS if totals[cat]["count"] > 0]
    available = [cat for cat in CATEGORY_WEIGHTS if question_counts[cat]["planned"] > 0]

    # Category averages (0-10) over all planned questions, unasked ones as 0.
    category_avgs = {
        cat: (totals[cat]["total"] / question_counts[cat]["planned"])
        if question_counts[cat]["planned"]
        else 0.0
        for cat in CATEGORY_WEIGHTS
    }

    # Points earned per category, out of its weight.
    raw_scores = {
        cat: (category_avgs[cat] / 10.0) * CATEGORY_WEIGHTS[cat] for cat in CATEGORY_WEIGHTS
    }

    total_raw_score = sum(raw_scores.values())
    max_possible_score = sum(CATEGORY_WEIGHTS[cat] for cat in available)
    overall_score = (
        round(total_raw_score / max_possible_score * 10.0, 1) if max_possible_score else 0.0
    )

    return {
        "category_averages": {cat: round(avg, 1) for cat, avg in category_avgs.items()},
        "raw_scores": {cat: round(score, 1) for cat, score in raw_scores.items()},
        "category_max_scores": dict(CATEGORY_WEIGHTS),
        "categories_asked": asked,
        "category_question_counts": question_counts,
        "total_raw_score": round(total_raw_score, 1),
        "max_possible_score": max_possible_score,
        "overall_score": overall_score,
    }


def initialize_queues(questions: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Group generated questions into queues by category."""
    queues: Dict[str, List[Dict[str, Any]]] = {cat: [] for cat in CATEGORIES_ORDER}
    for q in questions:
        cat = q.get("category", "must_have_matched")
        if cat in queues:
            queues[cat].append(q)
    return queues


def get_next_question(
    question_queues: Dict[str, List[Dict]],
    evaluations: List[Dict],
) -> Tuple[Optional[Dict], Optional[str]]:
    """Pick the next question using dynamic chunk-based routing.

    Returns ``(next_question_obj, termination_reason)``.
    * Normal flow: ``(question_dict, None)``
    * Interview complete: ``(None, "questions_completed")``
    * Early termination: ``(None, "fatal_failure")``

    Routing rules
    ─────────────
    1. Questions are asked in chunks of ``CHUNK_SIZE`` per category.
    2. After completing a chunk (or when the current queue empties), a
       **checkpoint** fires and the rolling average is evaluated.
    3. **avg > threshold** → *recovery / continue*:
       Walk **backwards** through ``CATEGORIES_ORDER`` from the current
       position to find a previous category with remaining questions
       (this is the "recovery" path after a downgrade). If nothing is
       behind, continue the current queue or advance forward.
    4. **avg ≤ threshold** → *downgrade*:
       Walk **forwards** through ``CATEGORIES_ORDER`` to the next
       category that still has questions. If nothing is ahead, trigger
       ``fatal_failure``.
    """
    # ── Count how many questions have been answered per category ──────────
    cat_counts: Dict[str, int] = {cat: 0 for cat in CATEGORIES_ORDER}
    for e in evaluations:
        c = e.get("category", "must_have_matched")
        if c in cat_counts:
            cat_counts[c] += 1

    total_asked = sum(cat_counts.values())

    # ── First question: pick from first non-empty queue ──────────────────
    if total_asked == 0:
        for cat in CATEGORIES_ORDER:
            if question_queues.get(cat):
                return question_queues[cat].pop(0), None
        return None, "questions_completed"

    # ── Determine current state ──────────────────────────────────────────
    current_category = evaluations[-1].get("category", "must_have_matched")
    rolling_avg = calculate_rolling_average(evaluations)
    current_queue_empty = not question_queues.get(current_category)
    questions_in_chunk = cat_counts.get(current_category, 0) % CHUNK_SIZE

    # Checkpoint fires when a full chunk just completed OR current queue is
    # exhausted (partial chunk).
    is_checkpoint = (questions_in_chunk == 0) or current_queue_empty

    # ── Mid-chunk: stay on current category ──────────────────────────────
    if not is_checkpoint:
        return question_queues[current_category].pop(0), None

    # ── CHECKPOINT DECISION ──────────────────────────────────────────────
    curr_idx = (
        CATEGORIES_ORDER.index(current_category)
        if current_category in CATEGORIES_ORDER
        else 0
    )

    if rolling_avg > DOWNGRADE_THRESHOLD:
        # Candidate is doing well.
        # 1. Recovery: walk backwards to find a previous category with
        #    remaining questions (handles the "come back to must_have after
        #    recovering in domain" flow).
        for i in range(curr_idx - 1, -1, -1):
            cat = CATEGORIES_ORDER[i]
            if question_queues.get(cat):
                return question_queues[cat].pop(0), None

        # 2. Continue current category if it still has questions.
        if question_queues.get(current_category):
            return question_queues[current_category].pop(0), None

        # 3. Advance forward to the next category with questions.
        for i in range(curr_idx + 1, len(CATEGORIES_ORDER)):
            cat = CATEGORIES_ORDER[i]
            if question_queues.get(cat):
                return question_queues[cat].pop(0), None

        # All queues exhausted → interview complete.
        return None, "questions_completed"
    else:
        # Candidate is struggling → downgrade forward.
        for i in range(curr_idx + 1, len(CATEGORIES_ORDER)):
            cat = CATEGORIES_ORDER[i]
            if question_queues.get(cat):
                return question_queues[cat].pop(0), None

        # No forward categories available → fatal failure.
        return None, "fatal_failure"
