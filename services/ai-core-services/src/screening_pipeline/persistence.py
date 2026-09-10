"""Persistence helpers for completed questions and interview close (no websocket I/O)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.screening_pipeline.evaluator import AnswerEvaluator
from src.screening_pipeline.session_api import SessionApiClient
from src.llm.client import OllamaClient
from src.screening_pipeline.routing_engine import calculate_final_weighted_score
from src.screening_pipeline.prompts import FINAL_QUALITATIVE_SUMMARY_PROMPT, RECOMMENDATION_THRESHOLD
from src.common.llm_utils import parse_llm_json
import json


async def persist_completed_question(
    api_client: SessionApiClient,
    analysis_evaluations: List[Dict[str, Any]],
    *,
    question_obj: dict,
    current_q: str,
    transcript: str,
    primary_eval: dict,
    current_eval: dict,
    question_number: int,
    follow_ups: Optional[list],
) -> Optional[Dict[str, Any]]:
    """Save Q&A and evaluation; retain only evaluations saved by Core API."""
    qa_entry = AnswerEvaluator.build_qa_entry(
        question_obj, current_q, transcript, question_number, follow_ups
    )
    await api_client.save_transcript(qa_entry)

    evaluation = AnswerEvaluator.build_evaluation_block(
        question_obj,
        current_q,
        transcript,
        primary_eval,
        current_eval,
        question_number,
        follow_ups,
    )
    if await api_client.save_evaluation(evaluation):
        analysis_evaluations.append(evaluation)
        return evaluation
    return None


async def persist_interview_close(
    api_client: SessionApiClient,
    llm_client: OllamaClient,
    evaluations: List[Dict[str, Any]],
    transcript_log: List[Dict[str, Any]],
) -> None:
    """Persist final summary and full conversational transcript."""
    if not evaluations:
        return
        
    summary_math = calculate_final_weighted_score(evaluations)
    
    prompt = FINAL_QUALITATIVE_SUMMARY_PROMPT.format(
        category_scores=json.dumps(summary_math["category_averages"], indent=2),
        transcript=json.dumps(evaluations, indent=2)
    )
    
    interview_summary_points = []
    try:
        res = await llm_client.openai_chat_generate(
            prompt=prompt, 
            system="You are a strict JSON returning AI.", 
            temperature=0.2
        )
        parsed = parse_llm_json(res.response)
        if isinstance(parsed, dict) and "interview_summary" in parsed:
            interview_summary_points = parsed["interview_summary"]
    except Exception as e:
        interview_summary_points = ["Evaluation complete, but failed to generate qualitative summary."]

    final_summary_payload = {
        "total_score": summary_math["total_raw_score"],
        "max_possible_score": 100.0,
        "overall_score": summary_math["overall_score"],
        "final_recommendation": "shortlist_for_l1" if summary_math["overall_score"] >= RECOMMENDATION_THRESHOLD else "reject",
        "interview_summary": interview_summary_points
    }
    
    await api_client.save_final_summary(final_summary_payload)
    await api_client.save_interview_metadata(transcript_log)
