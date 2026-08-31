import json
from typing import Any

from src.llm.client import OllamaClient
from src.core.logger import logger
from src.question_generation.schemas import (
    GenerateQuestionsRequest,
    GenerateQuestionsResponse,
    GeneratedQuestion,
)
from src.question_generation.prompt_builder import question_prompt_builder
from src.question_generation.match_context import neutral_job_fit_analysis
from src.common.llm_utils import parse_llm_json


def _parse_questions(raw: Any) -> list[GeneratedQuestion]:
    parsed_questions = parse_llm_json(raw) if isinstance(raw, str) else raw

    if isinstance(parsed_questions, dict):
        for key in ("questions", "generated_questions", "data"):
            if key in parsed_questions and isinstance(parsed_questions[key], list):
                parsed_questions = parsed_questions[key]
                break

    if not isinstance(parsed_questions, list):
        raise ValueError(f"Expected JSON array, got {type(parsed_questions).__name__}")

    return [GeneratedQuestion(**q) for q in parsed_questions]


class QuestionGenerator:
    """Orchestrates the question generation pipeline."""

    def __init__(self):
        self.llm_client = OllamaClient()

    async def _call_llm(self, prompt: str, *, log_extra: dict[str, Any]) -> list[GeneratedQuestion]:
        logger.info("Sending question generation prompt to LLM", extra=log_extra)
        response = await self.llm_client.openai_chat_generate(
            prompt=prompt, temperature=0.3, timeout=120.0
        )
        return _parse_questions(response.response)

    async def generate(self, request: GenerateQuestionsRequest) -> GenerateQuestionsResponse:
        """Generate tailored interview questions for a candidate session or job bank."""
        log_extra = {"interview_session_id": request.interview_session_id}
        try:
            match_result = request.job_fit_analysis or neutral_job_fit_analysis(
                request.parsed_jd
            )
            prompt = question_prompt_builder.build(
                parsed_jd=request.parsed_jd,
                match_result=match_result,
            )
            questions = await self._call_llm(prompt, log_extra=log_extra)
            logger.info(
                "Successfully generated interview questions",
                extra={**log_extra, "count": len(questions)},
            )
            return GenerateQuestionsResponse(
                interview_session_id=request.interview_session_id,
                status="success",
                questions=questions,
                count=len(questions),
            )
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse question generation JSON output: {e}", extra=log_extra)
            return GenerateQuestionsResponse(
                interview_session_id=request.interview_session_id,
                status="error",
                error_message=f"LLM returned invalid JSON: {str(e)}",
            )
        except Exception as e:
            logger.error(f"Unexpected error during question generation: {e}", extra=log_extra)
            return GenerateQuestionsResponse(
                interview_session_id=request.interview_session_id,
                status="error",
                error_message=str(e),
            )


question_generator = QuestionGenerator()
