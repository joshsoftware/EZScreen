"""
Answer Evaluator for the AI Screening Pipeline.
Handles intent routing, answer evaluation, and evaluation result building.
"""
import json
from typing import Dict, Any, Optional, Tuple, List
from src.core.logger import logger
from src.llm.client import OllamaClient
from src.screening_pipeline.prompts import (
    INTENT_ROUTER_SYSTEM,
    ANSWER_EVALUATION_SYSTEM,
)


class AnswerEvaluator:
    """Evaluates candidate answers using LLM-based intent routing and scoring."""

    def __init__(self, llm_client: OllamaClient):
        self.llm_client = llm_client

    async def route_intent(self, current_question: str, transcript: str) -> Tuple[str, str]:
        """
        Classifies the candidate's speech into an intent.
        Returns: (intent, ai_response)
        """
        intent_prompt = f"Current Interview Question: {current_question}\nCandidate Speech: {transcript}"

        try:
            intent_res = await self.llm_client.openai_chat_generate(
                prompt=intent_prompt,
                system=INTENT_ROUTER_SYSTEM,
                temperature=0.1
            )
            raw_text = intent_res.response.replace("```json", "").replace("```", "").strip()
            data = json.loads(raw_text)
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
        follow_up_context: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Evaluates the candidate's answer against expected keywords and strictness.
        Returns the full eval_data dict from the LLM.
        """
        # Build the user prompt
        full_context = "You are evaluating a candidate's answer in a FIRST SCREENING interview.\n\n"

        if follow_up_context:
            full_context += "NOTE: This is a FOLLOW-UP evaluation. The candidate had an insufficient primary answer.\n\n"

        full_context += f"QUESTION: {current_question}\n"

        candidate_answer = ""
        if follow_up_context:
            for fu in follow_up_context:
                candidate_answer += f"AI: {fu.get('ai_response', '')}\nCandidate: {fu.get('candidate_speech', '')}\n"
        candidate_answer += f"Candidate Latest Answer: {transcript}"

        full_context += f"CANDIDATE ANSWER: {candidate_answer}\n"
        full_context += f"EXPECTED KEYWORDS (answer should address most of these): {expected_keywords}\n"
        full_context += f"EVALUATION STRICTNESS LEVEL: {answer_depth}\n"

        try:
            eval_res = await self.llm_client.openai_chat_generate(
                prompt=full_context,
                system=ANSWER_EVALUATION_SYSTEM,
                temperature=0.2
            )
            raw_text = eval_res.response.replace("```json", "").replace("```", "").strip()
            eval_data = json.loads(raw_text)
        except Exception as e:
            logger.error("Answer evaluation failed", extra={"error": str(e)})
            eval_data = {
                "score": 0, "coverage_percent": 0,
                "keywords_found": [], "keywords_missing": [],
                "is_sufficient": False, "decision": "NEXT_QUESTION",
                "feedback": "Evaluation failed due to an internal error.",
                "suggested_follow_up": ""
            }

        decision = eval_data.get("decision", "NEXT_QUESTION")
        follow_up_question = eval_data.get("suggested_follow_up", "")

        if decision == "REPEAT_QUESTION":
            follow_up_question = "I'm sorry, could you please repeat your answer?"

        logger.info("Answer evaluated", extra={
            "decision": decision,
            "score": eval_data.get("score"),
            "keywords_missing": eval_data.get("keywords_missing", []),
        })

        return eval_data

    @staticmethod
    def build_skip_evaluation(question_obj: Dict, transcript: str) -> Dict[str, Any]:
        """Builds a 0-score evaluation for skipped questions."""
        return {
            "question_id": question_obj.get("id"),
            "question": question_obj.get("question", ""),
            "candidate_answer": transcript,
            "score": 0,
            "coverage_percent": 0,
            "keywords_found": [],
            "keywords_missing": question_obj.get("expected_keywords", []),
            "decision": "NEXT_QUESTION",
            "feedback": "Candidate chose to skip this question."
        }

    @staticmethod
    def build_evaluation_block(
        question_obj: Dict,
        current_q: str,
        transcript: str,
        primary_eval: Optional[Dict],
        current_eval: Dict,
        follow_ups: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """Builds the final evaluation block for analysis_result.evaluations[]."""
        # Use primary_eval for the top-level scores if this was a follow-up completion
        source = primary_eval if primary_eval else current_eval

        evaluation = {
            "question_id": question_obj.get("id"),
            "question": current_q,
            "candidate_answer": transcript,
            "score": source.get("score", 0),
            "coverage_percent": source.get("coverage_percent", 0),
            "keywords_found": source.get("keywords_found", []),
            "keywords_missing": source.get("keywords_missing", []),
            "decision": source.get("decision", "NEXT_QUESTION"),
            "feedback": source.get("feedback", "")
        }

        # Attach follow-up evaluation data
        if follow_ups:
            follow_up_data = []
            for fu in follow_ups:
                follow_up_data.append({
                    "follow_up_question": fu.get("ai_response", ""),
                    "follow_up_answer": fu.get("candidate_speech", ""),
                    "score": current_eval.get("score", 0),
                    "coverage_percent": current_eval.get("coverage_percent", 0),
                    "keywords_found": current_eval.get("keywords_found", []),
                    "keywords_missing": current_eval.get("keywords_missing", []),
                    "decision": current_eval.get("decision", "NEXT_QUESTION"),
                    "feedback": current_eval.get("feedback", "")
                })
            evaluation["follow_ups"] = follow_up_data

        return evaluation

    @staticmethod
    def build_qa_entry(
        question_obj: Dict,
        current_q: str,
        transcript: str,
        follow_ups: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """Builds the clean Q&A entry for question_answer column."""
        qa_entry = {
            "question_id": question_obj.get("id"),
            "bot_speech": current_q,
            "candidate_answer": transcript
        }

        if follow_ups:
            qa_follow_ups = []
            for fu in follow_ups:
                qa_follow_ups.append({
                    "bot_speech": fu.get("ai_response", ""),
                    "candidate_answer": fu.get("candidate_speech", "")
                })
            qa_entry["follow_ups"] = qa_follow_ups

        return qa_entry
