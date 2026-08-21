import asyncio
from fastapi import APIRouter
from src.job_fit_analysis.schemas import MatchRequest, MatchResponse
from src.job_fit_analysis.matcher import job_fit_matcher
from src.core.logger import logger

router = APIRouter(tags=["Matching"])

@router.post("/resume-jd", response_model=MatchResponse)
async def match_endpoint(request: MatchRequest):
    """
    Performs AI Job Fit Analysis by comparing a Parsed Resume against a Parsed JD.
    """
    logger.info("Received single matching request.")

    try:
        match_score_json = await job_fit_matcher.analyze_fit(
            resume_data=request.parsed_resume,
            jd_data=request.parsed_jd
        )
        return {
            "application_id": request.application_id,
            "job_id": request.job_id,
            "status": "success",
            "job_fit_analysis": match_score_json
        }
    except Exception as e:
        logger.error(f"Error matching application {request.application_id}: {e}")
        return {
            "application_id": request.application_id,
            "job_id": request.job_id,
            "status": "error",
            "error_message": str(e)
        }
