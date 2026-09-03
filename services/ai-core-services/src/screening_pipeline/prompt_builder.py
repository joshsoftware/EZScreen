"""User-prompt builders for the AI screening pipeline.

System prompt constants remain in prompts.py; this module builds the
per-request user prompts passed to the LLM.
"""

from __future__ import annotations

from typing import Dict, List, Optional


class ScreeningPromptBuilder:
    """Builds LLM user prompts for intent routing and answer evaluation."""

    def build_intent_prompt(self, current_question: str, transcript: str) -> str:
        return (
            f"Current Interview Question: {current_question}\n"
            f"Candidate Speech: {transcript}"
        )

    def build_evaluation_prompt(
        self,
        current_question: str,
        transcript: str,
        expected_keywords: str,
        answer_depth: str,
        follow_up_context: Optional[List[Dict]] = None,
    ) -> str:
        parts = [
            "You are evaluating a candidate's answer in a FIRST SCREENING interview.\n",
        ]

        if follow_up_context:
            parts.append(
                "NOTE: This is a FOLLOW-UP evaluation. "
                "The candidate had an insufficient primary answer.\n"
            )

        parts.append(f"QUESTION: {current_question}\n")

        candidate_answer = ""
        if follow_up_context:
            for fu in follow_up_context:
                candidate_answer += (
                    f"AI: {fu.get('ai_response', '')}\n"
                    f"Candidate: {fu.get('candidate_speech', '')}\n"
                )
        candidate_answer += f"Candidate Latest Answer: {transcript}"

        parts.append(f"CANDIDATE ANSWER: {candidate_answer}\n")
        parts.append(
            f"EXPECTED KEYWORDS (answer should address most of these): {expected_keywords}\n"
        )
        parts.append(f"EVALUATION STRICTNESS LEVEL: {answer_depth}\n")

        return "\n".join(parts)


screening_prompt_builder = ScreeningPromptBuilder()
