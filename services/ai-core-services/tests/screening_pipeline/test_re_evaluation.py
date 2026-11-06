"""HR re-evaluation re-scores saved answers the way the live interview does."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.screening_pipeline.re_evaluation import re_evaluate_screening

QUESTIONS = [
    {
        "id": 7,
        "question": "HashMap vs ConcurrentHashMap?",
        "category": "must_have_matched",
        "expected_keywords": ["thread-safe", "segment locking", "null keys"],
        "answer_depth": "full_depth",
    }
]


def _scored(score, missing=()):
    return {
        "intent": "ANSWERING",
        "score": score,
        "coverage_percent": score * 10,
        "keywords_found": [],
        "keywords_missing": list(missing),
        "decision": "NEXT_QUESTION" if score >= 4 else "ASK_FOLLOW_UP",
        "feedback": f"scored {score}",
    }


async def _run(saved, evaluate):
    summary = {"overall_score": 5.0, "total_score": 50.0}
    with patch(
        "src.screening_pipeline.re_evaluation.AnswerEvaluator.classify_and_evaluate",
        evaluate,
    ), patch(
        "src.screening_pipeline.re_evaluation.build_final_summary",
        AsyncMock(return_value=summary),
    ) as build:
        result = await re_evaluate_screening(MagicMock(), saved, QUESTIONS)
    return result, build


@pytest.mark.asyncio
async def test_answer_is_scored_with_the_questions_keywords_and_depth():
    evaluate = AsyncMock(return_value=_scored(8))
    saved = [{
        "question_id": 1,
        "question": "HashMap vs ConcurrentHashMap?",
        "category": "must_have_matched",
        "candidate_answer": "ConcurrentHashMap is thread-safe.",
        "score": 2,
    }]

    result, build = await _run(saved, evaluate)

    call = evaluate.await_args.kwargs
    assert call["transcript"] == "ConcurrentHashMap is thread-safe."
    assert call["expected_keywords"] == "thread-safe, segment locking, null keys"
    assert call["answer_depth"] == "full_depth"
    [evaluation] = result["evaluations"]
    assert evaluation["question_id"] == 1
    assert evaluation["score"] == 8
    assert build.await_args.kwargs["termination_reason"] == "re_evaluation"
    assert result["final_summary"]["overall_score"] == 5.0


@pytest.mark.asyncio
async def test_follow_up_is_scored_on_what_the_main_answer_missed():
    evaluate = AsyncMock(side_effect=[_scored(3, missing=["segment locking"]), _scored(6)])
    saved = [{
        "question_id": 1,
        "question": "HashMap vs ConcurrentHashMap?",
        "category": "must_have_matched",
        "candidate_answer": "One is thread-safe.",
        "follow_ups": [{"follow_up_question": "How does it lock?", "follow_up_answer": "Per bucket."}],
    }]

    result, _ = await _run(saved, evaluate)

    follow_up_call = evaluate.await_args_list[1].kwargs
    assert follow_up_call["expected_keywords"] == "segment locking"
    assert follow_up_call["transcript"] == "Per bucket."
    [evaluation] = result["evaluations"]
    assert evaluation["score"] == 3
    assert evaluation["follow_ups"][0]["score"] == 6
    assert evaluation["follow_ups"][0]["follow_up_answer"] == "Per bucket."


@pytest.mark.asyncio
async def test_empty_or_non_answers_score_zero():
    evaluate = AsyncMock(return_value={"intent": "SMALL_TALK", "response": "ok"})
    saved = [
        {"question_id": 1, "question": "Q?", "candidate_answer": "   "},
        {"question_id": 2, "question": "HashMap vs ConcurrentHashMap?", "candidate_answer": "next question"},
    ]

    result, _ = await _run(saved, evaluate)

    assert evaluate.await_count == 1  # the empty answer never reaches the AI
    assert [e["score"] for e in result["evaluations"]] == [0, 0]
    assert result["evaluations"][1]["keywords_missing"] == QUESTIONS[0]["expected_keywords"]


@pytest.mark.asyncio
async def test_only_corrected_answers_are_marked_again():
    """Re-marking unchanged text moved a borderline answer from 4 to 3."""
    evaluate = AsyncMock(return_value=_scored(7))
    saved = [
        {"question_id": 1, "question": "HashMap vs ConcurrentHashMap?", "candidate_answer": "kept", "score": 4},
        {"question_id": 2, "question": "HashMap vs ConcurrentHashMap?", "candidate_answer": "corrected", "score": 1},
    ]
    summary = {"overall_score": 5.0}
    with patch(
        "src.screening_pipeline.re_evaluation.AnswerEvaluator.classify_and_evaluate", evaluate
    ), patch(
        "src.screening_pipeline.re_evaluation.build_final_summary", AsyncMock(return_value=summary)
    ) as build:
        result = await re_evaluate_screening(MagicMock(), saved, QUESTIONS, rescore_question_ids=[2])

    assert evaluate.await_count == 1
    assert evaluate.await_args.kwargs["transcript"] == "corrected"
    assert [e["score"] for e in result["evaluations"]] == [4, 7]
    # Totals are still rebuilt from every question, with the plan.
    assert build.await_args.kwargs["planned_questions"] == QUESTIONS
