import json

from fastapi import APIRouter

from src.core.logger import logger
from src.parsing.jd_parser import jd_parser
from src.parsing.resume_parser import resume_parser
from src.parsing.schemas import (
    ParseResumeRequest,
    ParsedJDResponse,
    ParsedResumeResponse,
    RawJDRequest,
)

router = APIRouter(tags=["Parsing"])


@router.post("/resume", response_model=ParsedResumeResponse)
async def parse_resume_endpoint(request: ParseResumeRequest):
    """Parses a single resume."""
    logger.info(f"Received parse request for resume: {request.resume_name}")

    try:
        parsed_json = await resume_parser.parse_s3_file(s3_key=request.resume_path)
        return {
            "resume_name": request.resume_name,
            "status": "success",
            "parsed_resume": parsed_json,
        }
    except Exception as e:
        logger.error(f"Error parsing resume {request.resume_path}: {e}")
        return {
            "resume_name": request.resume_name,
            "status": "error",
            "error_message": str(e),
        }


@router.post("/jd", response_model=ParsedJDResponse)
async def parse_jd_endpoint(request: RawJDRequest):
    """Parses a single JD from a raw JSON payload."""
    logger.info("Received parse request for JD.")

    try:
        jd_text = json.dumps(request.model_dump(), indent=2)
        parsed_json = await jd_parser.parse_jd_text(jd_text)
        return {
            "status": "success",
            "parsed_jd": parsed_json,
        }
    except Exception as e:
        logger.error(f"Error parsing JD: {e}")
        return {
            "status": "error",
            "error_message": str(e),
        }
