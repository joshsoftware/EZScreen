"""Comprehensive tests for the dynamic routing engine.

Covers: normal flow, downgrade, recovery (backward), fatal failure,
partial chunks, single-question categories, empty categories,
weighted scoring, and rolling average calculation.
"""

import pytest

from src.screening_pipeline.routing_engine import (
    CATEGORIES_ORDER,
    CHUNK_SIZE,
    DOWNGRADE_THRESHOLD,
    calculate_final_weighted_score,
    calculate_rolling_average,
    get_next_question,
    initialize_queues,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_questions(mh=0, dom=0, gth=0, lack=0):
    """Create a question list with the given count per category."""
    questions = []
    idx = 1
    for i in range(mh):
        questions.append({"id": idx, "category": "must_have_matched", "question": f"MH-{i+1}"})
        idx += 1
    for i in range(dom):
        questions.append({"id": idx, "category": "experience_domain", "question": f"DOM-{i+1}"})
        idx += 1
    for i in range(gth):
        questions.append({"id": idx, "category": "good_to_have", "question": f"GTH-{i+1}"})
        idx += 1
    for i in range(lack):
        questions.append({"id": idx, "category": "lacking_skill", "question": f"LACK-{i+1}"})
        idx += 1
    return questions


def _run_interview(questions, scores):
    """Simulate an interview returning (asked_questions, evaluations, reason)."""
    queues = initialize_queues(questions)
    evaluations = []
    asked = []
    score_idx = 0

    for _ in range(50):  # safety cap
        q, reason = get_next_question(queues, evaluations)
        if q is None:
            return asked, evaluations, reason
        score = scores[score_idx] if score_idx < len(scores) else 5
        evaluations.append({"category": q["category"], "score": score})
        asked.append(q["question"])
        score_idx += 1

    return asked, evaluations, "max_iterations"


# ─── Configuration Tests ─────────────────────────────────────────────────────

def test_chunk_size_is_three():
    assert CHUNK_SIZE == 3


def test_downgrade_threshold_is_three():
    assert DOWNGRADE_THRESHOLD == 3.0


def test_categories_order():
    assert CATEGORIES_ORDER == [
        "must_have_matched",
        "experience_domain",
        "good_to_have",
        "lacking_skill",
    ]


# ─── initialize_queues Tests ─────────────────────────────────────────────────

def test_initialize_queues_groups_by_category():
    questions = _make_questions(mh=3, dom=2, gth=1, lack=2)
    queues = initialize_queues(questions)

    assert len(queues["must_have_matched"]) == 3
    assert len(queues["experience_domain"]) == 2
    assert len(queues["good_to_have"]) == 1
    assert len(queues["lacking_skill"]) == 2


def test_initialize_queues_unknown_category_dropped():
    questions = [{"id": 1, "category": "unknown_cat", "question": "Q1"}]
    queues = initialize_queues(questions)

    for cat in CATEGORIES_ORDER:
        assert len(queues[cat]) == 0


def test_initialize_queues_missing_category_defaults_to_must_have():
    questions = [{"id": 1, "question": "Q1"}]  # no category key
    queues = initialize_queues(questions)

    assert len(queues["must_have_matched"]) == 1


# ─── calculate_rolling_average Tests ─────────────────────────────────────────

def test_rolling_average_empty():
    assert calculate_rolling_average([]) == 0.0


def test_rolling_average_simple():
    evals = [{"score": 8}, {"score": 6}, {"score": 4}]
    assert calculate_rolling_average(evals) == 6.0


def test_rolling_average_with_follow_up():
    evals = [
        {"score": 4, "follow_ups": [{"score": 8}]},  # topic avg = 6
        {"score": 6, "follow_ups": []},                # topic avg = 6
    ]
    assert calculate_rolling_average(evals) == 6.0


def test_rolling_average_ignores_non_dict():
    evals = [{"score": 8}, None, "garbage", {"score": 4}]
    # Only the two dicts count: (8 + 4) / 2 = 6.0
    assert calculate_rolling_average(evals) == 6.0


# ─── get_next_question: Normal Flow ──────────────────────────────────────────

def test_normal_flow_all_questions_asked():
    """Good candidate → all questions asked in category order."""
    questions = _make_questions(mh=7, dom=3, gth=4, lack=2)
    scores = [7] * 16
    asked, evals, reason = _run_interview(questions, scores)

    assert reason == "questions_completed"
    assert len(asked) == 16
    # Must-have comes first
    assert asked[0] == "MH-1"
    assert asked[6] == "MH-7"
    # Then domain
    assert asked[7] == "DOM-1"


def test_normal_flow_first_question_from_must_have():
    """First question is always from the first non-empty category."""
    questions = _make_questions(mh=3, dom=1, gth=1, lack=1)
    queues = initialize_queues(questions)
    q, reason = get_next_question(queues, [])

    assert q["category"] == "must_have_matched"
    assert reason is None


def test_first_question_skips_empty_categories():
    """If must_have is empty, first question comes from next available."""
    questions = _make_questions(mh=0, dom=2, gth=1, lack=1)
    queues = initialize_queues(questions)
    q, reason = get_next_question(queues, [])

    assert q["category"] == "experience_domain"


# ─── get_next_question: Checkpoint at Chunk Boundary ─────────────────────────

def test_checkpoint_fires_after_chunk_size():
    """After 3 MH questions (chunk complete), engine evaluates avg."""
    questions = _make_questions(mh=7, dom=3, gth=3, lack=2)
    queues = initialize_queues(questions)
    evaluations = []

    # Ask 3 MH with high scores → should continue MH
    for _ in range(3):
        q, _ = get_next_question(queues, evaluations)
        evaluations.append({"category": q["category"], "score": 7})

    # 4th question should still be MH (avg > 3, no previous categories)
    q, _ = get_next_question(queues, evaluations)
    assert q["category"] == "must_have_matched"
    assert q["question"] == "MH-4"


def test_checkpoint_fires_when_queue_empties():
    """Partial chunk: category with 2 questions forces checkpoint at 2."""
    questions = _make_questions(mh=2, dom=3, gth=3, lack=2)
    scores = [7] * 10
    asked, evals, reason = _run_interview(questions, scores)

    assert reason == "questions_completed"
    assert len(asked) == 10
    # MH-1, MH-2 asked, then queue empty → checkpoint → move to DOM
    assert asked[0:2] == ["MH-1", "MH-2"]
    assert asked[2] == "DOM-1"


# ─── get_next_question: Downgrade ────────────────────────────────────────────

def test_downgrade_on_low_avg():
    """avg ≤ 3 after MH chunk → downgrade to domain."""
    questions = _make_questions(mh=7, dom=3, gth=3, lack=2)
    queues = initialize_queues(questions)
    evaluations = []

    # 3 MH with low scores
    for _ in range(3):
        q, _ = get_next_question(queues, evaluations)
        evaluations.append({"category": q["category"], "score": 2})

    # Next should be DOM (downgrade)
    q, _ = get_next_question(queues, evaluations)
    assert q["category"] == "experience_domain"


def test_downgrade_cascades_through_all_categories():
    """Continuous failure → MH → DOM → GTH → LACK in order."""
    questions = _make_questions(mh=7, dom=3, gth=3, lack=2)
    scores = [1] * 20
    asked, evals, reason = _run_interview(questions, scores)

    categories_seen = [e["category"] for e in evals]
    # Should see MH first, then DOM, then GTH, then LACK
    assert categories_seen[0] == "must_have_matched"
    assert categories_seen[3] == "experience_domain"
    assert categories_seen[6] == "good_to_have"
    assert categories_seen[9] == "lacking_skill"


def test_downgrade_exact_threshold_triggers():
    """Score of exactly 3.0 triggers downgrade (threshold is strict >)."""
    questions = _make_questions(mh=6, dom=3, gth=3, lack=2)
    queues = initialize_queues(questions)
    evaluations = []

    # 3 MH with score exactly 3 → avg = 3.0 → should downgrade
    for _ in range(3):
        q, _ = get_next_question(queues, evaluations)
        evaluations.append({"category": q["category"], "score": 3})

    q, _ = get_next_question(queues, evaluations)
    assert q["category"] == "experience_domain"


# ─── get_next_question: Recovery (Backward) ──────────────────────────────────

def test_recovery_goes_back_to_previous_category():
    """After downgrade to DOM + high scores → recover back to MH."""
    questions = _make_questions(mh=7, dom=3, gth=3, lack=2)
    scores = [2, 2, 2, 8, 8, 8] + [7] * 20
    asked, evals, reason = _run_interview(questions, scores)

    assert reason == "questions_completed"
    # First 3: MH, then 3: DOM (downgrade), then back to MH (recovery)
    assert asked[0:3] == ["MH-1", "MH-2", "MH-3"]
    assert asked[3:6] == ["DOM-1", "DOM-2", "DOM-3"]
    assert asked[6] == "MH-4"  # recovered!


def test_recovery_goes_to_nearest_previous_with_questions():
    """Recovery walks backwards: if at LACK and recovers, goes to GTH first."""
    questions = _make_questions(mh=6, dom=3, gth=6, lack=3)
    queues = initialize_queues(questions)
    evaluations = []

    # Simulate: 3 MH (fail) → 3 DOM (fail) → 3 GTH (fail) → 3 LACK (pass)
    for _ in range(3):
        q, _ = get_next_question(queues, evaluations)
        evaluations.append({"category": q["category"], "score": 1})  # MH fail
    for _ in range(3):
        q, _ = get_next_question(queues, evaluations)
        evaluations.append({"category": q["category"], "score": 1})  # DOM fail
    for _ in range(3):
        q, _ = get_next_question(queues, evaluations)
        evaluations.append({"category": q["category"], "score": 1})  # GTH fail
    for _ in range(3):
        q, _ = get_next_question(queues, evaluations)
        evaluations.append({"category": q["category"], "score": 10})  # LACK pass

    # Now avg should be above 3 → recovery → should go to GTH (nearest previous)
    q, _ = get_next_question(queues, evaluations)
    assert q["category"] == "good_to_have"


def test_recovery_skips_empty_previous_categories():
    """If previous category is exhausted, recovery goes further back."""
    questions = _make_questions(mh=6, dom=3, gth=3, lack=3)
    queues = initialize_queues(questions)
    evaluations = []

    # 3 MH (fail) → 3 DOM (all asked, queue empty) → fail → 3 GTH (pass)
    for _ in range(3):
        q, _ = get_next_question(queues, evaluations)
        evaluations.append({"category": q["category"], "score": 2})  # MH fail
    for _ in range(3):
        q, _ = get_next_question(queues, evaluations)
        evaluations.append({"category": q["category"], "score": 2})  # DOM fail (all 3 asked)
    for _ in range(3):
        q, _ = get_next_question(queues, evaluations)
        evaluations.append({"category": q["category"], "score": 9})  # GTH pass

    # DOM is empty, so recovery should go to MH (which still has 3 remaining)
    q, _ = get_next_question(queues, evaluations)
    assert q["category"] == "must_have_matched"


# ─── get_next_question: Fatal Failure ────────────────────────────────────────

def test_fatal_failure_when_all_categories_exhausted_with_low_avg():
    """Fail all categories → fatal_failure."""
    questions = _make_questions(mh=7, dom=3, gth=3, lack=2)
    scores = [1] * 20
    asked, evals, reason = _run_interview(questions, scores)

    assert reason == "fatal_failure"
    # Should have asked: 3 MH + 3 DOM + 3 GTH + 2 LACK = 11
    assert len(asked) == 11


def test_fatal_failure_skips_remaining_questions():
    """Fatal failure leaves un-asked questions in the queues."""
    questions = _make_questions(mh=7, dom=3, gth=3, lack=2)
    queues = initialize_queues(questions)
    evaluations = []

    # Ask all with score 1
    for _ in range(20):
        q, reason = get_next_question(queues, evaluations)
        if q is None:
            break
        evaluations.append({"category": q["category"], "score": 1})

    assert reason == "fatal_failure"
    # MH should still have 4 remaining (asked 3 out of 7)
    assert len(queues["must_have_matched"]) == 4


# ─── get_next_question: Partial Chunks ───────────────────────────────────────

def test_partial_chunk_single_question_category():
    """Category with only 1 question: asked, then checkpoint forces."""
    questions = _make_questions(mh=7, dom=1, gth=4, lack=2)
    scores = [7] * 14
    asked, evals, reason = _run_interview(questions, scores)

    assert reason == "questions_completed"
    assert len(asked) == 14
    assert "DOM-1" in asked


def test_partial_chunk_two_question_category():
    """Category with 2 questions: both asked before forced checkpoint."""
    questions = _make_questions(mh=6, dom=2, gth=3, lack=2)
    scores = [7] * 13
    asked, evals, reason = _run_interview(questions, scores)

    assert reason == "questions_completed"
    assert "DOM-1" in asked
    assert "DOM-2" in asked


def test_single_question_per_category():
    """Every category has exactly 1 question."""
    questions = _make_questions(mh=1, dom=1, gth=1, lack=1)
    scores = [7] * 4
    asked, evals, reason = _run_interview(questions, scores)

    assert reason == "questions_completed"
    assert len(asked) == 4


# ─── get_next_question: Empty Categories ─────────────────────────────────────

def test_empty_category_skipped():
    """Category with 0 questions is skipped entirely."""
    questions = _make_questions(mh=7, dom=0, gth=3, lack=2)
    scores = [7] * 12
    asked, evals, reason = _run_interview(questions, scores)

    assert reason == "questions_completed"
    assert len(asked) == 12
    assert all(not q.startswith("DOM") for q in asked)


def test_all_queues_empty_returns_completed():
    """No questions at all → immediate questions_completed."""
    queues = initialize_queues([])
    q, reason = get_next_question(queues, [])

    assert q is None
    assert reason == "questions_completed"


# ─── calculate_final_weighted_score Tests ─────────────────────────────────────

def test_weighted_score_basic():
    """Verify the 50/20/20/10 math."""
    evaluations = [
        {"category": "must_have_matched", "score": 8},
        {"category": "must_have_matched", "score": 6},
        {"category": "experience_domain", "score": 7},
        {"category": "good_to_have", "score": 5},
        {"category": "lacking_skill", "score": 4},
    ]
    result = calculate_final_weighted_score(evaluations)

    assert result["category_averages"]["must_have_matched"] == 7.0
    assert result["category_averages"]["experience_domain"] == 7.0
    assert result["category_averages"]["good_to_have"] == 5.0
    assert result["category_averages"]["lacking_skill"] == 4.0
    # MH: 7/10*50=35, DOM: 7/10*20=14, GTH: 5/10*20=10, LACK: 4/10*10=4
    assert result["total_raw_score"] == 63.0
    assert result["overall_score"] == 6.3


def test_weighted_score_empty_category_redistributes():
    """Unasked category weight goes to must_have."""
    evaluations = [
        {"category": "must_have_matched", "score": 10},
        {"category": "good_to_have", "score": 10},
        {"category": "lacking_skill", "score": 10},
        # No experience_domain questions asked
    ]
    result = calculate_final_weighted_score(evaluations)

    # DOM weight (20) redistributed to MH (50→70)
    assert result["raw_scores"]["experience_domain"] == 0.0
    # MH: 10/10*70=70, GTH: 10/10*20=20, LACK: 10/10*10=10
    assert result["total_raw_score"] == 100.0
    assert result["overall_score"] == 10.0


def test_weighted_score_all_zeros():
    """All scores 0 → overall score is 0."""
    evaluations = [
        {"category": "must_have_matched", "score": 0},
        {"category": "experience_domain", "score": 0},
        {"category": "good_to_have", "score": 0},
        {"category": "lacking_skill", "score": 0},
    ]
    result = calculate_final_weighted_score(evaluations)

    assert result["overall_score"] == 0.0


def test_weighted_score_with_follow_ups():
    """Follow-up scores are averaged with the primary score."""
    evaluations = [
        {"category": "must_have_matched", "score": 4, "follow_ups": [{"score": 8}]},
        # topic avg = (4 + 8) / 2 = 6
    ]
    result = calculate_final_weighted_score(evaluations)

    assert result["category_averages"]["must_have_matched"] == 6.0


def test_weighted_score_empty_evaluations():
    """No evaluations → all zeros."""
    result = calculate_final_weighted_score([])

    assert result["overall_score"] == 0.0
    assert result["total_raw_score"] == 0.0
