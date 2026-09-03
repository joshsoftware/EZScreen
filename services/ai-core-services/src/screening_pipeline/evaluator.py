"""
Answer Evaluator for the AI Screening Pipeline.
Handles intent routing, answer evaluation, and evaluation result building.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from src.common.llm_utils import parse_llm_json
from src.core.logger import logger
from src.llm.client import OllamaClient
from src.screening_pipeline.evaluation_builders import (
    build_evaluation_block,
    build_qa_entry,
    build_skip_evaluation,
)
from src.screening_pipeline.prompt_builder import screening_prompt_builder
from src.screening_pipeline.prompts import (
    ANSWER_EVALUATION_SYSTEM,
    INTENT_ROUTER_SYSTEM,
)

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


class AnswerEvaluator:
    """Evaluates candidate answers using LLM-based intent routing and scoring."""

    def __init__(self, llm_client: OllamaClient):
        self.llm_client = llm_client

    async def route_intent(self, current_question: str, transcript: str) -> Tuple[str, str]:
        """Classify candidate speech. Returns (intent, ai_response)."""
        intent_prompt = screening_prompt_builder.build_intent_prompt(
            current_question, transcript
        )

        try:
            intent_res = await self.llm_client.openai_chat_generate(
                prompt=intent_prompt,
                system=INTENT_ROUTER_SYSTEM,
                temperature=0.1,
            )
            data = parse_llm_json(intent_res.response)
            if not isinstance(data, dict):
                raise ValueError("Intent router expected a JSON object")
            intent = data.get("intent", "ANSWERING")
            ai_response = data.get("response", "")
        except Exception as e:
            logger.error("Intent routing failed", extra={"error": str(e)})
            intent = "ANSWERING"
            ai_response = ""

        logger.info("Intent routed", extra={"intent": intent})
        return intent, ai_response

    async def evaluate_answer(
        self,
        current_question: str,
        transcript: str,
        expected_keywords: str,
        answer_depth: str,
        follow_up_context: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """Evaluate answer against keywords/strictness. Returns LLM eval_data dict."""
        full_context = screening_prompt_builder.build_evaluation_prompt(
            current_question=current_question,
            transcript=transcript,
            expected_keywords=expected_keywords,
            answer_depth=answer_depth,
            follow_up_context=follow_up_context,
        )

        try:
            eval_res = await self.llm_client.openai_chat_generate(
                prompt=full_context,
                system=ANSWER_EVALUATION_SYSTEM,
                temperature=0.2,
            )
            eval_data = parse_llm_json(eval_res.response)
            if not isinstance(eval_data, dict):
                raise ValueError("Answer evaluation expected a JSON object")
        except Exception as e:
            logger.error("Answer evaluation failed", extra={"error": str(e)})
            eval_data = dict(_EVAL_FAILURE_FALLBACK)

        decision = eval_data.get("decision", "NEXT_QUESTION")
        if decision == "REPEAT_QUESTION":
            eval_data["suggested_follow_up"] = (
                "I'm sorry, could you please repeat your answer?"
            )

        logger.info(
            "Answer evaluated",
            extra={
                "decision": decision,
                "score": eval_data.get("score"),
                "keywords_missing": eval_data.get("keywords_missing", []),
            },
        )

        return eval_data

    # Keep static wrappers for existing call sites on AnswerEvaluator
    build_skip_evaluation = staticmethod(build_skip_evaluation)
    build_evaluation_block = staticmethod(build_evaluation_block)
    build_qa_entry = staticmethod(build_qa_entry)
