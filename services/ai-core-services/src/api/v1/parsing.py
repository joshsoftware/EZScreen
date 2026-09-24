import json
import os
import tempfile

from fastapi import APIRouter, File, UploadFile

from src.core.logger import logger
from src.parsing.jd_parser import jd_parser
from src.parsing.resume_parser import resume_parser
from src.parsing.schemas import (
    JDFormPrefillResponse,
    ParseResumeRequest,
    ParsedJDResponse,
    ParsedResumeResponse,
    RawJDRequest,
)

router = APIRouter(tags=["Parsing"])

_MAX_JD_UPLOAD_BYTES = 10 * 1024 * 1024
_ALLOWED_JD_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/markdown",
    "application/msword",
    "application/octet-stream",
}


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


@router.post("/jd/form-prefill", response_model=JDFormPrefillResponse)
async def parse_jd_form_prefill_endpoint(file: UploadFile = File(...)):
    """Extract JD file text and map into Create Job form sections."""
    file_name = file.filename or "jd"
    logger.info("Received JD form-prefill request for %s", file_name)

    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type and content_type not in _ALLOWED_JD_CONTENT_TYPES:
        ext = os.path.splitext(file_name)[1].lower()
        if ext not in {".pdf", ".txt", ".md", ".docx"}:
            return {
                "status": "error",
                "form": None,
                "error_message": "Unsupported file type. Upload PDF, DOCX, or TXT.",
            }

    tmp_path = None
    try:
        raw = await file.read()
        if not raw:
            return {
                "status": "error",
                "form": None,
                "error_message": "Uploaded file is empty",
            }
        if len(raw) > _MAX_JD_UPLOAD_BYTES:
            return {
                "status": "error",
                "form": None,
                "error_message": "JD file must be 10 MB or smaller",
            }

        ext = os.path.splitext(file_name)[1].lower() or ".bin"
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(raw)
            tmp_path = tmp.name

        jd_text = jd_parser.extract_text_from_file(tmp_path)
        form_data = await jd_parser.sectionize_for_form(jd_text)
        return {
            "status": "success",
            "form": form_data,
            "error_message": None,
        }
    except Exception as e:
        logger.error("Error in JD form-prefill for %s: %s", file_name, e)
        return {
            "status": "error",
            "form": None,
            "error_message": str(e),
        }
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
