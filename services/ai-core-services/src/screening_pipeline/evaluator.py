"""
Answer Evaluator for the AI Screening Pipeline.
Handles intent routing, answer evaluation, and evaluation result building.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.common.llm_utils import parse_llm_json
from src.core.logger import logger
from src.llm.client import OllamaClient
from src.screening_pipeline.evaluation_builders import (
    build_evaluation_block,
    build_qa_entry,
    build_skip_evaluation,
)
from src.screening_pipeline.prompt_builder import screening_prompt_builder
from src.screening_pipeline.prompts import FOLLOW_UP_SCORE_THRESHOLD, UNIFIED_SCREENING_SYSTEM

_EVAL_FAILURE_FALLBACK = {
    "score": 0,
    "coverage_percent": 0,
    "keywords_found": [],
    "keywords_missing": [],
    "is_sufficient": False,
    "decision": "NEXT_QUESTION",
    "feedback": "Evaluation failed due to an internal error.",
    "suggested_follow_up": "",
}


def _coerce_score(value: Any) -> float:
    """Return a bounded numeric LLM answer-quality score."""
    try:
        return max(0.0, min(10.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _split_expected_keywords(expected_keywords: str) -> List[str]:
    """Return the de-duplicated, order-preserving expected-keyword list."""
    unique: List[str] = []
    seen: set[str] = set()
    for keyword in expected_keywords.split(","):
        cleaned = keyword.strip()
        normalized = cleaned.casefold()
        if cleaned and normalized not in seen:
            unique.append(cleaned)
            seen.add(normalized)
    return unique


def _resolve_keywords_found(llm_found: Any, expected: List[str]) -> List[str]:
    """Keep only LLM-reported keywords that are in the expected list.

    The LLM decides which keywords the candidate covered; anything it returns
    that is not an expected keyword (invented, renamed) is discarded, and the
    expected list's own spelling and order are preserved.
    """
    if not isinstance(llm_found, list):
        return []
    reported = {str(item).strip().casefold() for item in llm_found}
    return [keyword for keyword in expected if keyword.casefold() in reported]


class AnswerEvaluator:
    """Evaluates candidate answers using LLM-based intent routing and scoring."""

    def __init__(self, llm_client: OllamaClient):
        self.llm_client = llm_client

    async def classify_and_evaluate(
        self,
        current_question: str,
        transcript: str,
        expected_keywords: str,
        answer_depth: str,
        follow_up_context: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """Single LLM call: classify candidate intent and, if ANSWERING, score the answer.

        Replaces the previous two-call route_intent + evaluate_answer sequence to cut
        one full model round-trip off every turn. Returns at least {"intent", "response"};
        when intent is ANSWERING it also carries the same evaluation fields
        evaluate_answer used to return (score, decision, feedback, etc.).
        """
        prompt = screening_prompt_builder.build_unified_prompt(
            current_question=current_question,
            transcript=transcript,
            expected_keywords=expected_keywords,
            answer_depth=answer_depth,
            follow_up_context=follow_up_context,
        )

        try:
            res = await self.llm_client.openai_chat_generate(
                prompt=prompt,
                system=UNIFIED_SCREENING_SYSTEM,
                temperature=0.2,
            )
            data = parse_llm_json(res.response)
            if not isinstance(data, dict):
                raise ValueError("Unified screening call expected a JSON object")
        except Exception as e:
            logger.error("Unified screening call failed", extra={"error": str(e)})
            # A failed classification is treated as an attempted answer that failed
            # evaluation, matching the old behavior where a route_intent failure
            # defaulted to ANSWERING and then evaluate_answer scored it as 0.
            data = {"intent": "ANSWERING", "response": "", **_EVAL_FAILURE_FALLBACK}

        intent = data.get("intent", "ANSWERING")
        ai_response = data.get("response", "")

        logger.info("Intent routed", extra={"intent": intent})

        if intent != "ANSWERING":
            return {"intent": intent, "response": ai_response}

        eval_data = self._apply_scores(data, expected_keywords)
        eval_data["intent"] = intent
        eval_data["response"] = ai_response

        logger.info(
            "Answer evaluated",
            extra={
                "decision": eval_data.get("decision"),
                "score": eval_data.get("score"),
                "keywords_missing": eval_data.get("keywords_missing", []),
            },
        )

        return eval_data

    @staticmethod
    def _apply_scores(
        eval_data: Dict[str, Any], expected_keywords: str
    ) -> Dict[str, Any]:
        """Combine the LLM's keyword_match_score and answer_quality_score into the 50/50 final score.

        The LLM judges keyword coverage and returns its score directly. The
        application only bounds it, cleans the keyword lists against the expected
        keywords, and does the final blend and decision.
        """
        expected = _split_expected_keywords(expected_keywords)
        keywords_found = _resolve_keywords_found(eval_data.get("keywords_found"), expected)
        keywords_missing = [keyword for keyword in expected if keyword not in keywords_found]

        answer_quality_score = _coerce_score(
            eval_data.get("answer_quality_score", eval_data.get("score"))
        )
        if not expected:
            # Nothing to match, so the quality score stands in for the keyword component.
            keyword_match_score = answer_quality_score
        elif eval_data.get("keyword_match_score") is not None:
            keyword_match_score = _coerce_score(eval_data["keyword_match_score"])
        else:
            # LLM omitted the score: fall back to its own keyword list.
            keyword_match_score = round(len(keywords_found) / len(expected) * 10, 1)
        coverage_percent = round(keyword_match_score * 10)
        final_score = round((keyword_match_score + answer_quality_score) / 2)

        eval_data["keywords_found"] = keywords_found
        eval_data["keywords_missing"] = keywords_missing
        eval_data["coverage_percent"] = coverage_percent
        eval_data["keyword_match_score"] = keyword_match_score
        eval_data["answer_quality_score"] = answer_quality_score
        eval_data["score"] = final_score

        decision = eval_data.get("decision", "NEXT_QUESTION")
        if decision == "REPEAT_QUESTION":
            eval_data["suggested_follow_up"] = (
                "I'm sorry, could you please repeat your answer?"
            )
            eval_data["is_sufficient"] = False
        else:
            decision = (
                "NEXT_QUESTION" if final_score >= FOLLOW_UP_SCORE_THRESHOLD else "ASK_FOLLOW_UP"
            )
            eval_data["decision"] = decision
            eval_data["is_sufficient"] = decision == "NEXT_QUESTION"

        return eval_data

    # Keep static wrappers for existing call sites on AnswerEvaluator
    build_skip_evaluation = staticmethod(build_skip_evaluation)
    build_evaluation_block = staticmethod(build_evaluation_block)
    build_qa_entry = staticmethod(build_qa_entry)
