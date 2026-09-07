from fastapi import APIRouter
from src.question_generation.schemas import GenerateQuestionsRequest, GenerateQuestionsResponse
from src.question_generation.generator import question_generator
from src.core.logger import logger

router = APIRouter(tags=["Question Generation"])


@router.post("/generate", response_model=GenerateQuestionsResponse)
async def generate_questions_endpoint(request: GenerateQuestionsRequest):
    """
    Generates tailored interview screening questions.

    Candidate sessions: Core API sends parsed_jd, job_fit_analysis, and optional parsed_resume.
    Job-level banks (legacy): send parsed_jd only (job id as interview_session_id).
    """
    logger.info(
        f"Received question generation request for session: {request.interview_session_id}"
    )
    return await question_generator.generate(request)
