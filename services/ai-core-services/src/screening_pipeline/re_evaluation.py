"""Re-score a finished screening from its saved answers (HR "Re-evaluate").

Answers HR corrected (the speech-to-text misheard them) are marked again
with the same evaluator and evaluation builder the live interview uses; the
others keep their marks, since re-marking unchanged text only adds drift.
The weighted total and summary are then rebuilt from all of them with the
current scoring rules.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from src.core.logger import logger
from src.llm.client import OllamaClient
from src.screening_pipeline.evaluation_builders import build_evaluation_block
from src.screening_pipeline.evaluator import AnswerEvaluator
from src.screening_pipeline.persistence import build_final_summary
from src.screening_pipeline.tts_prewarm import coerce_questions_list

DEFAULT_ANSWER_DEPTH = "partial_depth"


def _question_for(saved: Dict[str, Any], questions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """The generated question a saved evaluation was asked from.

    Saved evaluations keep the question text but not its expected keywords or
    depth; match on the text. Fall back to the keywords the first scoring saw.
    """
    text = str(saved.get("question") or "").strip()
    for question in questions:
        if str(question.get("question") or "").strip() == text:
            return question
    keywords = list(saved.get("keywords_found") or []) + list(saved.get("keywords_missing") or [])
    return {
        "question": text,
        "category": saved.get("category", "must_have_matched"),
        "expected_keywords": keywords,
        "answer_depth": DEFAULT_ANSWER_DEPTH,
    }


def _no_answer_evaluation(feedback: str) -> Dict[str, Any]:
    return {
        "score": 0,
        "coverage_percent": 0,
        "keywords_found": [],
        "keywords_missing": [],
        "decision": "NEXT_QUESTION",
        "feedback": feedback,
    }


async def _score(
    evaluator: AnswerEvaluator,
    *,
    question: str,
    answer: str,
    expected_keywords: List[str],
    answer_depth: str,
    follow_up_context: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    if not answer.strip():
        return _no_answer_evaluation("No answer was given.")
    result = await evaluator.classify_and_evaluate(
        current_question=question,
        transcript=answer,
        expected_keywords=", ".join(expected_keywords),
        answer_depth=answer_depth,
        follow_up_context=follow_up_context,
    )
    if result.get("intent", "ANSWERING") != "ANSWERING":
        # A skip, "I don't know" or small talk: nothing to score.
        return {
            **_no_answer_evaluation("The reply does not answer the question."),
            "keywords_missing": expected_keywords,
        }
    return result


async def _re_evaluate_one(
    evaluator: AnswerEvaluator,
    saved: Dict[str, Any],
    questions: List[Dict[str, Any]],
) -> Dict[str, Any]:
    question_obj = _question_for(saved, questions)
    question_text = str(saved.get("question") or question_obj.get("question") or "")
    answer = str(saved.get("candidate_answer") or "")
    expected = [str(k) for k in question_obj.get("expected_keywords") or []]

    primary = await _score(
        evaluator,
        question=question_text,
        answer=answer,
        expected_keywords=expected,
        answer_depth=question_obj.get("answer_depth", DEFAULT_ANSWER_DEPTH),
    )

    follow_ups = [
        {
            "ai_response": str(fu.get("follow_up_question") or ""),
            "candidate_speech": str(fu.get("follow_up_answer") or ""),
        }
        for fu in saved.get("follow_ups") or []
        if isinstance(fu, dict) and str(fu.get("follow_up_answer") or "").strip()
    ]
    current = primary
    if follow_ups:
        # As live: the follow-up is judged on what the main answer missed.
        last = follow_ups[-1]
        current = await _score(
            evaluator,
            question=last["ai_response"],
            answer=last["candidate_speech"],
            expected_keywords=list(primary.get("keywords_missing") or []),
            answer_depth=DEFAULT_ANSWER_DEPTH,
            follow_up_context=[{**fu, "candidate_speech": ""} for fu in follow_ups[-1:]],
        )

    return build_evaluation_block(
        question_obj,
        question_text,
        answer,
        primary if follow_ups else None,
        current,
        int(saved.get("question_id") or 0),
        follow_ups or None,
    )


async def _keep(saved: Dict[str, Any]) -> Dict[str, Any]:
    return dict(saved)


async def re_evaluate_screening(
    llm_client: OllamaClient,
    saved_evaluations: List[Dict[str, Any]],
    generated_questions: Any,
    rescore_question_ids: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """New evaluations (same order and question ids) and the final summary.

    Only questions in `rescore_question_ids` are marked again; None re-marks
    every question.
    """
    evaluator = AnswerEvaluator(llm_client)
    questions = coerce_questions_list(generated_questions)
    rescore = None if rescore_question_ids is None else set(rescore_question_ids)
    evaluations = await asyncio.gather(
        *(
            _re_evaluate_one(evaluator, saved, questions)
            if rescore is None or saved.get("question_id") in rescore
            else _keep(saved)
            for saved in saved_evaluations
        )
    )
    final_summary = await build_final_summary(
        llm_client,
        list(evaluations),
        termination_reason="re_evaluation",
        planned_questions=questions,
    )
    logger.info(
        "Re-evaluated screening answers",
        extra={
            "questions": len(evaluations),
            "re_marked": len(evaluations) if rescore is None else len(rescore),
            "overall_score": final_summary.get("overall_score"),
        },
    )
    return {"evaluations": list(evaluations), "final_summary": final_summary}
