"""
Dynamic Routing Engine for AI Screening Pipeline.
Handles chunk-based state transitions, rolling average calculations,
and backward recovery after downgrades.
"""

from typing import Any, Dict, List, Tuple, Optional

from src.screening_pipeline.summary_calculator import _score

# ─── Configuration ────────────────────────────────────────────────────────────
CHUNK_SIZE = 3            # Evaluate every N questions per category
DOWNGRADE_THRESHOLD = 3.0  # Rolling average at or below this triggers a downgrade

# Priority order: must-have first, then domain, good-to-have, lacking last.
# Weights are out of 100 and are the single source for the final summary.
CATEGORY_WEIGHTS = {
    "must_have_matched": 60,
    "experience_domain": 20,
    "good_to_have": 10,
    "lacking_skill": 10,
}
CATEGORIES_ORDER = list(CATEGORY_WEIGHTS)

# Every screening opens with these compulsory questions, in this order:
# 2 must-have, 1 domain, 2 must-have, 1 domain, 1 good-to-have, 1 skill gap.
CORE_SEQUENCE = [
    "must_have_matched",
    "must_have_matched",
    "experience_domain",
    "must_have_matched",
    "must_have_matched",
    "experience_domain",
    "good_to_have",
    "lacking_skill",
]
# After them, the interview continues only if they score at least this
# (out of 10, with the final-result weights); otherwise it ends early.
CORE_CONTINUE_THRESHOLD = 5.0
# Earlier check: a candidate clearly failing the first few compulsory
# questions (mostly skipped / very weak) is stopped there.
EARLY_CHECK_AFTER = 4
EARLY_STOP_THRESHOLD = 3.0


def calculate_rolling_average(evaluations: List[Dict[str, Any]]) -> float:
    """Calculate the rolling average of evaluated topics."""
    persisted_evaluations = [item for item in evaluations if isinstance(item, dict)]
    persisted_question_count = len(persisted_evaluations)
    if persisted_question_count == 0:
        return 0.0

    total_score = 0.0
    for evaluation in persisted_evaluations:
        primary_score = _score(evaluation.get("score"))
        follow_ups = evaluation.get("follow_ups", [])
        first_follow_up = follow_ups[0] if isinstance(follow_ups, list) and follow_ups else None

        if isinstance(first_follow_up, dict) and first_follow_up.get("score") is not None:
            topic_score = (primary_score + _score(first_follow_up["score"])) / 2
        else:
            topic_score = primary_score

        total_score += topic_score

    return round(total_score / persisted_question_count, 1)


def calculate_final_weighted_score(evaluations: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate the 60/20/10/10 weighted score based on category averages."""
    categories = {
        cat: {"weight": weight, "total": 0.0, "count": 0}
        for cat, weight in CATEGORY_WEIGHTS.items()
    }

    # Sum up topic scores by category
    for evaluation in evaluations:
        category = evaluation.get("category")
        if category not in categories:
            continue

        primary_score = _score(evaluation.get("score"))
        follow_ups = evaluation.get("follow_ups", [])
        first_follow_up = follow_ups[0] if isinstance(follow_ups, list) and follow_ups else None

        if isinstance(first_follow_up, dict) and first_follow_up.get("score") is not None:
            topic_score = (primary_score + _score(first_follow_up["score"])) / 2
        else:
            topic_score = primary_score

        categories[category]["total"] += topic_score
        categories[category]["count"] += 1

    # Calculate category averages (0-10)
    category_avgs = {}
    for cat, data in categories.items():
        if data["count"] > 0:
            category_avgs[cat] = data["total"] / data["count"]
        else:
            category_avgs[cat] = 0.0

    # Redistribute weights for unasked categories to must_have_matched
    effective_weights = {cat: data["weight"] for cat, data in categories.items()}
    for cat in ["experience_domain", "good_to_have", "lacking_skill"]:
        if categories[cat]["count"] == 0:
            effective_weights["must_have_matched"] += effective_weights[cat]
            effective_weights[cat] = 0

    # Calculate raw scaled scores (out of 100)
    raw_scores = {}
    for cat in categories:
        # avg (0-10) / 10 = (0-1.0) * weight
        raw_scores[cat] = (category_avgs[cat] / 10.0) * effective_weights[cat]

    total_raw_score = sum(raw_scores.values())
    overall_score = round(total_raw_score / 10.0, 1)

    return {
        "category_averages": {cat: round(avg, 1) for cat, avg in category_avgs.items()},
        "raw_scores": {cat: round(score, 1) for cat, score in raw_scores.items()},
        "total_raw_score": round(total_raw_score, 1),
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


def _pop_core_question(
    question_queues: Dict[str, List[Dict]], category: str
) -> Optional[Dict]:
    """The next question of `category`; if that category has run out, the
    next one in priority order, so the compulsory set still has 8 questions."""
    if question_queues.get(category):
        return question_queues[category].pop(0)
    for cat in CATEGORIES_ORDER:
        if question_queues.get(cat):
            return question_queues[cat].pop(0)
    return None


def core_phase_score(evaluations: List[Dict]) -> float:
    """Score (0-10) of the compulsory questions answered so far, with the
    final-result weights."""
    return calculate_final_weighted_score(evaluations[: len(CORE_SEQUENCE)])["overall_score"]


def get_next_question(
    question_queues: Dict[str, List[Dict]],
    evaluations: List[Dict],
) -> Tuple[Optional[Dict], Optional[str]]:
    """Pick the next question.

    1. The first len(CORE_SEQUENCE) questions are compulsory and follow
       CORE_SEQUENCE (M, M, D, M, M, D, G, S).
    2. After EARLY_CHECK_AFTER of them, a score below EARLY_STOP_THRESHOLD
       ends the interview there ("not_eligible_early").
    3. After all of them, the interview goes on only if they scored at least
       CORE_CONTINUE_THRESHOLD; otherwise it ends early ("not_eligible").
    4. The remaining questions use the adaptive routing
       (get_adaptive_next_question); the policy stops them at the time limit.

    Deterministic in (queues, evaluations), so an interview resumed after a
    restart picks up the same question.
    """
    asked = len(evaluations)
    if asked == EARLY_CHECK_AFTER and core_phase_score(evaluations) < EARLY_STOP_THRESHOLD:
        return None, "not_eligible_early"
    if asked < len(CORE_SEQUENCE):
        question = _pop_core_question(question_queues, CORE_SEQUENCE[asked])
        return (question, None) if question else (None, "questions_completed")

    if asked == len(CORE_SEQUENCE):
        if not any(question_queues.get(cat) for cat in CATEGORIES_ORDER):
            return None, "questions_completed"
        if core_phase_score(evaluations) < CORE_CONTINUE_THRESHOLD:
            return None, "not_eligible"

    return get_adaptive_next_question(question_queues, evaluations)


def get_adaptive_next_question(
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
