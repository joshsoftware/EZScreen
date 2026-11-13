"""Compulsory questions first, then continue only if the candidate is on track.

Every screening opens with 8 compulsory questions in a fixed order
(must-have x2, domain, must-have x2, domain, good-to-have, skill gap).
* After the first 4, a score below 3/10 ends the interview there.
* After all 8, the interview goes on only if they score at least 5/10.
* A candidate who goes on is stopped by the booked interview time.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.screening_pipeline.persistence import build_final_summary
from src.screening_pipeline.routing_engine import (
    CORE_CONTINUE_THRESHOLD,
    CORE_SEQUENCE,
    EARLY_CHECK_AFTER,
    EARLY_STOP_THRESHOLD,
    core_phase_score,
    get_next_question,
    initialize_queues,
)

M, D, G, S = "must_have_matched", "experience_domain", "good_to_have", "lacking_skill"


def _questions(counts=None):
    counts = counts or {M: 8, D: 2, G: 3, S: 2}  # the usual 15
    out, qid = [], 1
    for cat, n in counts.items():
        for _ in range(n):
            out.append({"id": qid, "category": cat, "question": f"{cat} {qid}?"})
            qid += 1
    return out


def _run(score_for, counts=None, limit=30):
    """Ask questions until the router stops; score_for(i, q) gives each score."""
    queues = initialize_queues(_questions(counts))
    evaluations, asked = [], []
    for i in range(limit):
        q, reason = get_next_question(queues, evaluations)
        if q is None:
            return asked, evaluations, reason
        asked.append(q["category"])
        evaluations.append({"category": q["category"], "score": score_for(i, q), "follow_ups": []})
    raise AssertionError("router never stopped")


def test_the_compulsory_order_is_m_m_d_m_m_d_g_s():
    assert CORE_SEQUENCE == [M, M, D, M, M, D, G, S]
    assert CORE_CONTINUE_THRESHOLD == 5.0
    assert (EARLY_CHECK_AFTER, EARLY_STOP_THRESHOLD) == (4, 3.0)


def test_clearly_failing_candidate_is_stopped_after_four():
    """Skipping (0) or very weak answers: no need to ask the other 4."""
    asked, evaluations, reason = _run(lambda i, q: 0)
    assert asked == [M, M, D, M]
    assert reason == "not_eligible_early"

    asked, _, reason = _run(lambda i, q: 2)
    assert len(asked) == 4 and reason == "not_eligible_early"


def test_score_of_three_after_four_carries_on_to_all_eight():
    asked, _, reason = _run(lambda i, q: 3)
    assert asked == CORE_SEQUENCE
    assert reason == "not_eligible"  # 3/10 after the 8 is still below 5


def test_weak_candidate_is_stopped_after_the_eight():
    asked, evaluations, reason = _run(lambda i, q: 4)
    assert len(asked) == 8
    assert core_phase_score(evaluations) == 4.0
    assert reason == "not_eligible"


def test_candidate_scoring_five_or_more_gets_the_remaining_questions():
    asked, evaluations, reason = _run(lambda i, q: 5)
    assert asked[:8] == CORE_SEQUENCE
    assert core_phase_score(evaluations) == 5.0
    assert len(asked) == 15  # every question asked
    assert reason == "questions_completed"


def test_the_decision_uses_the_final_result_weights():
    """Strong must-haves (60%) carry a candidate past weak extras."""
    scores = {M: 7, D: 3, G: 0, S: 0}  # 0.6*7 + 0.2*3 = 4.8 -> below 5
    asked, _, reason = _run(lambda i, q: scores[q["category"]])
    assert reason == "not_eligible" and len(asked) == 8

    scores = {M: 8, D: 3, G: 0, S: 0}  # 0.6*8 + 0.2*3 = 5.4 -> continue
    asked, _, reason = _run(lambda i, q: scores[q["category"]])
    assert len(asked) > 8


def test_a_category_that_runs_out_is_filled_in_priority_order():
    """No skill-gap questions generated: the 8th slot takes a must-have."""
    asked, _, _ = _run(lambda i, q: 6, counts={M: 8, D: 2, G: 3, S: 0})
    assert asked[:8] == [M, M, D, M, M, D, G, M]


def test_screening_with_eight_or_fewer_questions_just_completes():
    asked, _, reason = _run(lambda i, q: 4, counts={M: 4, D: 2, G: 1, S: 1})
    assert asked == CORE_SEQUENCE
    assert reason == "questions_completed"  # nothing left to decide about


def test_routing_is_repeatable_for_a_resumed_interview():
    """Same answers so far -> same next question (resume after restart)."""
    first, _, _ = _run(lambda i, q: 6)
    second, _, _ = _run(lambda i, q: 6)
    assert first == second


@pytest.mark.asyncio
async def test_hr_summary_says_why_it_ended_even_without_the_ai_summary():
    llm = MagicMock()
    llm.openai_chat_generate = AsyncMock(side_effect=RuntimeError("402 Payment Required"))
    evaluations = [{"category": c, "score": 3, "follow_ups": []} for c in CORE_SEQUENCE]

    summary = await build_final_summary(llm, evaluations, termination_reason="not_eligible")

    first_line = summary["final_recommendation"].splitlines()[0]
    assert first_line == (
        "• Ended early: the 8 compulsory questions scored 3.0/10, "
        "below 5, so the remaining questions were not asked."
    )

    early = [{"category": c, "score": 1, "follow_ups": []} for c in CORE_SEQUENCE[:4]]
    summary = await build_final_summary(llm, early, termination_reason="not_eligible_early")
    assert summary["final_recommendation"].splitlines()[0] == (
        "• Ended early: the first 4 compulsory questions scored 1.0/10, "
        "below 3, so the remaining questions were not asked."
    )

    summary = await build_final_summary(llm, evaluations, termination_reason="time_limit")
    assert summary["final_recommendation"].splitlines()[0] == (
        "• Ended at the booked interview time; the remaining questions were not asked."
    )


# --- Booked time limit (after the compulsory questions) ---

import asyncio  # noqa: E402

from src.screening_pipeline.pipecat_policy import PipecatInterviewPolicy  # noqa: E402


def _policy_mid_interview(answered, minutes_ago, duration=30):
    policy = PipecatInterviewPolicy(
        "sess-time",
        evaluator=MagicMock(),
        llm_client=MagicMock(),
        api_client=MagicMock(),
        speech_output=AsyncMock(),
    )
    questions = _questions()
    policy.session = MagicMock(interview_metadata={"duration_minutes": duration})
    policy.questions = questions
    policy.question_queues = initialize_queues(questions)
    # The first `answered` compulsory questions are done.
    policy.analysis_evaluations = []
    for _ in range(answered):
        q, _ = get_next_question(policy.question_queues, policy.analysis_evaluations)
        policy.analysis_evaluations.append({"category": q["category"], "score": 7, "follow_ups": []})
    policy.is_active = True
    policy._close_interview = AsyncMock()
    policy._begin_listening = MagicMock()
    policy._interview_started_at = asyncio.get_running_loop().time() - minutes_ago * 60
    return policy


@pytest.mark.asyncio
async def test_last_two_minutes_allow_one_final_good_to_have_question_then_close():
    """Senior: in the last 2 minutes, ask a Good-to-have / Skill-gap question
    if one is left; running 1-2 minutes over is fine. Only one."""
    policy = _policy_mid_interview(answered=9, minutes_ago=28.5)
    await policy._ask_next_question()

    assert policy.current_question_obj["category"] == "good_to_have"
    assert policy._final_question_asked
    policy._close_interview.assert_not_awaited()

    # The candidate answers it; next time round the interview closes.
    await policy._ask_next_question()
    assert policy.termination_reason == "time_limit"
    policy._close_interview.assert_awaited_once()


@pytest.mark.asyncio
async def test_final_question_falls_back_to_skill_gap():
    policy = _policy_mid_interview(answered=9, minutes_ago=28.5)
    policy.question_queues["good_to_have"] = []
    policy.question_queues["lacking_skill"] = [
        {"id": 99, "category": "lacking_skill", "question": "Any Kubernetes experience?"}
    ]
    await policy._ask_next_question()
    assert policy.current_question_obj["category"] == "lacking_skill"


@pytest.mark.asyncio
async def test_no_good_to_have_or_skill_gap_left_closes_at_the_last_two_minutes():
    policy = _policy_mid_interview(answered=9, minutes_ago=28.5)
    policy.question_queues["good_to_have"] = []
    policy.question_queues["lacking_skill"] = []
    await policy._ask_next_question()

    assert policy.termination_reason == "time_limit"
    policy._close_interview.assert_awaited_once()
    policy.speech_output.assert_not_awaited()


@pytest.mark.asyncio
async def test_no_final_question_once_the_booked_time_has_passed():
    policy = _policy_mid_interview(answered=9, minutes_ago=31)
    await policy._ask_next_question()

    assert policy.termination_reason == "time_limit"
    policy._close_interview.assert_awaited_once()


@pytest.mark.asyncio
async def test_questions_continue_while_there_is_time():
    policy = _policy_mid_interview(answered=9, minutes_ago=20)
    await policy._ask_next_question()

    policy._close_interview.assert_not_awaited()
    policy.speech_output.assert_awaited()


@pytest.mark.asyncio
async def test_the_booked_duration_is_used():
    """A 45-minute booking still has time at minute 40."""
    policy = _policy_mid_interview(answered=9, minutes_ago=40, duration=45)
    await policy._ask_next_question()
    policy._close_interview.assert_not_awaited()


@pytest.mark.asyncio
async def test_the_time_limit_never_cuts_the_compulsory_questions():
    policy = _policy_mid_interview(answered=5, minutes_ago=29)
    await policy._ask_next_question()

    policy._close_interview.assert_not_awaited()
    policy.speech_output.assert_awaited()


@pytest.mark.asyncio
async def test_the_clock_starts_when_the_bot_greets_the_candidate():
    policy = PipecatInterviewPolicy(
        "sess-clock", evaluator=MagicMock(), llm_client=MagicMock(),
        api_client=MagicMock(), speech_output=AsyncMock(),
    )
    policy._begin_listening = MagicMock()
    assert policy._interview_started_at is None

    before = asyncio.get_running_loop().time()
    await policy._greet()

    assert policy._interview_started_at is not None
    assert policy._interview_started_at >= before


# --- No "let's move on" when the answer ends the interview ---

from src.screening_pipeline.prompts import MOVE_ON_TEXT  # noqa: E402


def _spoken_texts(policy):
    return [call.args[0] for call in policy.speech_output.await_args_list]


@pytest.mark.asyncio
async def test_skipping_the_deciding_question_goes_straight_to_the_closing():
    """Test 1: the 4th skip ends it; the bot must not promise a next question."""
    policy = _policy_mid_interview(answered=3, minutes_ago=5)
    for evaluation in policy.analysis_evaluations:
        evaluation["score"] = 0  # 3 skips so far
    question = policy.question_queues["must_have_matched"][0]

    await policy._move_on(question, question["question"], "skip", None, reason="skip")

    assert MOVE_ON_TEXT not in _spoken_texts(policy)
    policy._close_interview.assert_awaited_once()
    assert policy.termination_reason == "not_eligible_early"


@pytest.mark.asyncio
async def test_skipping_mid_interview_still_says_move_on_before_the_next_question():
    policy = _policy_mid_interview(answered=1, minutes_ago=5)
    question = policy.question_queues["must_have_matched"][0]

    await policy._move_on(question, question["question"], "skip", None, reason="skip")

    spoken = _spoken_texts(policy)
    assert spoken[0] == MOVE_ON_TEXT
    assert len(spoken) == 2  # then the next question itself
    policy._close_interview.assert_not_awaited()


@pytest.mark.asyncio
async def test_the_final_question_gets_no_follow_up():
    """A weak answer normally gets a follow-up; not on the final question in
    the last minutes, so the interview only runs 1-2 minutes over."""
    policy = PipecatInterviewPolicy(
        "sess-final", evaluator=MagicMock(), speech_output=AsyncMock(), api_client=MagicMock(),
    )
    policy.is_active = True
    policy._final_question_asked = True
    policy.transcript_log = [
        {"interaction_type": "question", "candidate_answer": "", "follow_ups": [], "question_repeat_count": 0}
    ]
    policy._complete_question = AsyncMock()
    question = {"question": "Have you used Redis?", "category": "good_to_have", "expected_keywords": []}

    await policy._handle_answer(
        question, question["question"], "Not much.",
        {"decision": "ASK_FOLLOW_UP", "suggested_follow_up": "What did you use it for?", "score": 2},
    )

    policy._complete_question.assert_awaited_once()
    assert policy.transcript_log[-1]["follow_ups"] == []
