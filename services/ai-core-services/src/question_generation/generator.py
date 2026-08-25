import json
from src.llm.client import OllamaClient
from src.core.logger import logger
from src.question_generation.schemas import (
    GenerateQuestionsRequest,
    GenerateQuestionsResponse,
    GeneratedQuestion,
)
from src.question_generation.prompt_builder import question_prompt_builder
from src.common.llm_utils import parse_llm_json


class QuestionGenerator:
    """Orchestrates the question generation pipeline.

    1. Builds the prompt from parsed_jd, parsed_resume, and job_fit_analysis
    2. Calls the LLM via OpenAI-compatible chat endpoint
    3. Parses the JSON array response
    4. Returns the questions to Core API (no DB write)
    """

    def __init__(self):
        self.llm_client = OllamaClient()

    async def generate(self, request: GenerateQuestionsRequest) -> GenerateQuestionsResponse:
        """Generate tailored interview questions for a candidate."""
        try:
            # 1. Build prompt
            prompt = question_prompt_builder.build(
                parsed_jd=request.parsed_jd,
                parsed_resume=request.parsed_resume,
                match_result=request.job_fit_analysis,
            )

            # 2. Call LLM
            logger.info(
                "Sending question generation prompt to LLM",
                extra={"interview_session_id": request.interview_session_id},
            )
            response = await self.llm_client.openai_chat_generate(
                prompt=prompt, temperature=0.3, timeout=120.0
            )

            # 3. Parse JSON array response
            parsed_questions = parse_llm_json(response.response)

            # Handle case where LLM wraps array in an object
            if isinstance(parsed_questions, dict):
                # Try common wrapper keys
                for key in ("questions", "generated_questions", "data"):
                    if key in parsed_questions and isinstance(parsed_questions[key], list):
                        parsed_questions = parsed_questions[key]
                        break

            if not isinstance(parsed_questions, list):
                raise ValueError(f"Expected JSON array, got {type(parsed_questions).__name__}")

            # 4. Validate each question against the schema
            questions = [GeneratedQuestion(**q) for q in parsed_questions]

            logger.info(
                "Successfully generated interview questions",
                extra={
                    "interview_session_id": request.interview_session_id,
                    "count": len(questions),
                },
            )

            return GenerateQuestionsResponse(
                interview_session_id=request.interview_session_id,
                status="success",
                questions=questions,
                count=len(questions),
            )

        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to parse question generation JSON output: {e}",
                extra={"interview_session_id": request.interview_session_id},
            )
            return GenerateQuestionsResponse(
                interview_session_id=request.interview_session_id,
                status="error",
                error_message=f"LLM returned invalid JSON: {str(e)}",
            )
        except Exception as e:
            logger.error(
                f"Unexpected error during question generation: {e}",
                extra={"interview_session_id": request.interview_session_id},
            )
            return GenerateQuestionsResponse(
                interview_session_id=request.interview_session_id,
                status="error",
                error_message=str(e),
            )


question_generator = QuestionGenerator()
