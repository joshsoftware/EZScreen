import asyncio
from fastapi import APIRouter
from src.job_fit_analysis.schemas import MatchRequest, MatchBulkRequest, MatchResponse
from src.job_fit_analysis.matcher import job_fit_matcher
from src.core.logger import logger

router = APIRouter(tags=["Matching"])

@router.post("/resume-jd", response_model=list[MatchResponse])
async def match_endpoint(request: MatchBulkRequest):
    """
    Performs AI Job Fit Analysis by comparing a Parsed Resume against a Parsed JD.
    """
    logger.info(f"Received bulk matching request for {len(request.matches)} candidates.")

    async def process_single(match_req: MatchRequest) -> dict:
        try:
            match_score_json = await job_fit_matcher.analyze_fit(
                resume_data=match_req.parsed_resume,
                jd_data=match_req.parsed_jd
            )
            return {
                "application_id": match_req.application_id,
                "job_id": match_req.job_id,
                "status": "success",
                "job_fit_analysis": match_score_json
            }
        except Exception as e:
            logger.error(f"Error matching application {match_req.application_id}: {e}")
            return {
                "application_id": match_req.application_id,
                "job_id": match_req.job_id,
                "status": "error",
                "error_message": str(e)
            }

    # Execute all matching requests concurrently
    tasks = [process_single(req) for req in request.matches]
    results = await asyncio.gather(*tasks)
    return results
