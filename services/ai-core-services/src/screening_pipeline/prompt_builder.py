"""User-prompt builders for the AI screening pipeline.

System prompt constants remain in prompts.py; this module builds the
per-request user prompts passed to the LLM.
"""

from __future__ import annotations

from typing import Dict, List, Optional


class ScreeningPromptBuilder:
    """Builds LLM user prompts for intent routing and answer evaluation."""

    def build_unified_prompt(
        self,
        current_question: str,
        transcript: str,
        expected_keywords: str,
        answer_depth: str,
        follow_up_context: Optional[List[Dict]] = None,
    ) -> str:
        """Build the single user prompt for combined intent classification + evaluation.

        Always carries evaluation context (question, keywords, strictness) even though
        it is only relevant when the system prompt determines intent is ANSWERING —
        the candidate's intent is not known until the LLM responds.
        """
        parts = [
            "You are processing one candidate turn in a FIRST SCREENING interview.\n",
        ]

        if follow_up_context:
            parts.append(
                "NOTE: If the candidate is ANSWERING, this is a FOLLOW-UP evaluation. "
                "The candidate had an insufficient primary answer.\n"
            )

        parts.append(f"CURRENT INTERVIEW QUESTION: {current_question}\n")

        candidate_answer = ""
        if follow_up_context:
            for fu in follow_up_context:
                candidate_answer += (
                    f"AI: {fu.get('ai_response', '')}\n"
                    f"Candidate: {fu.get('candidate_speech', '')}\n"
                )
        candidate_answer += f"Candidate Latest Speech: {transcript}"

        parts.append(f"CANDIDATE SPEECH: {candidate_answer}\n")
        parts.append(
            "EVALUATION CONTEXT (use only if intent is ANSWERING):\n"
            f"EXPECTED KEYWORDS (answer should address most of these): {expected_keywords}\n"
            f"EVALUATION STRICTNESS LEVEL: {answer_depth}\n"
        )

        return "\n".join(parts)


screening_prompt_builder = ScreeningPromptBuilder()
