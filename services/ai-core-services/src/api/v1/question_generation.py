from fastapi import APIRouter
from src.question_generation.schemas import GenerateQuestionsRequest, GenerateQuestionsResponse
from src.question_generation.generator import question_generator
from src.core.logger import logger

router = APIRouter(tags=["Question Generation"])


@router.post("/generate", response_model=GenerateQuestionsResponse)
async def generate_questions_endpoint(request: GenerateQuestionsRequest):
    """
    Generates tailored interview screening questions for a candidate.

    Core API sends parsed_resume, parsed_jd, and job_fit_analysis.
    AI service builds the prompt, calls the LLM, and returns the questions.
    Core API is responsible for saving the questions to interview_session.generated_questions.
    """
    logger.info(
        f"Received question generation request for session: {request.interview_session_id}"
    )

    return await question_generator.generate(request)
