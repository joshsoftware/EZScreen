import asyncio
from fastapi import APIRouter, HTTPException
from src.parsing.schemas import ParseResumeRequest, ParseResumeBulkRequest, ParsedResumeResponse
from src.parsing.resume_parser import resume_parser
from src.core.logger import logger

router = APIRouter(tags=["Parsing"])

@router.post("/resume", response_model=list[ParsedResumeResponse])
async def parse_resume_endpoint(request: ParseResumeBulkRequest):
    """
    Parses one or more resumes concurrently.
    Accepts an array of resumes. If you only have one resume, pass an array with a single item.
    """
    logger.info(f"Received bulk parse request for {len(request.resumes)} resumes.")

    async def process_single(resume_req: ParseResumeRequest) -> dict:
        try:
            parsed_json = await resume_parser.parse_s3_file(
                s3_key=resume_req.resume_path
            )
            return {
                "application_id": resume_req.application_id,
                "status": "success",
                "parsed_resume": parsed_json
            }
        except Exception as e:
            logger.error(f"Error parsing resume {resume_req.resume_path}: {e}")
            return {
                "application_id": resume_req.application_id,
                "status": "error",
                "error_message": str(e)
            }

    # Execute all parse requests concurrently
    tasks = [process_single(req) for req in request.resumes]
    results = await asyncio.gather(*tasks)
    return results
