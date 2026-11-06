from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.core.logger import logger
from src.llm import llm_client
from src.screening_pipeline.re_evaluation import re_evaluate_screening

router = APIRouter(tags=["Screening Re-evaluation"])


class ReEvaluateScreeningRequest(BaseModel):
    interview_session_id: str
    # analysis_result.evaluations as saved, with any answers HR corrected.
    evaluations: List[Dict[str, Any]] = Field(..., min_length=1)
    generated_questions: Any = None
    # Questions whose answer HR corrected; only these are marked again.
    # None (older callers) re-marks every question.
    rescore_question_ids: Optional[List[int]] = None


class ReEvaluateScreeningResponse(BaseModel):
    evaluations: List[Dict[str, Any]]
    final_summary: Dict[str, Any]


@router.post("/re-evaluate", response_model=ReEvaluateScreeningResponse)
async def re_evaluate_screening_endpoint(request: ReEvaluateScreeningRequest):
    """Re-score a finished screening's saved answers the way the live bot scores them."""
    logger.info(
        "Received screening re-evaluation request",
        extra={"session_id": request.interview_session_id, "questions": len(request.evaluations)},
    )
    return await re_evaluate_screening(
        llm_client,
        request.evaluations,
        request.generated_questions,
        request.rescore_question_ids,
    )
