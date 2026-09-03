import json
from typing import Any, Optional

from src.common.llm_utils import parse_llm_json
from src.core.logger import logger
from src.llm.client import OllamaClient
from src.question_generation.match_context import neutral_job_fit_analysis
from src.question_generation.prompt_builder import question_prompt_builder
from src.question_generation.question_parsing import parse_questions
from src.question_generation.schemas import (
    GenerateQuestionsRequest,
    GenerateQuestionsResponse,
    GeneratedQuestion,
)


class QuestionGenerator:
    """Orchestrates the question generation pipeline."""

    def __init__(self, llm_client: Optional[OllamaClient] = None):
        self.llm_client = llm_client or OllamaClient()

    async def _call_llm(self, prompt: str, *, log_extra: dict[str, Any]) -> list[GeneratedQuestion]:
        logger.info("Sending question generation prompt to LLM", extra=log_extra)
        response = await self.llm_client.openai_chat_generate(
            prompt=prompt, temperature=0.3, timeout=120.0
        )
        return parse_questions(response.response)

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
