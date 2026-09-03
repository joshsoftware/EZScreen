"""Persistence helpers for completed questions and interview close (no websocket I/O)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.screening_pipeline.evaluator import AnswerEvaluator
from src.screening_pipeline.session_api import SessionApiClient


async def persist_completed_question(
    api_client: SessionApiClient,
    analysis_evaluations: List[Dict[str, Any]],
    *,
    question_obj: dict,
    current_q: str,
    transcript: str,
    primary_eval: dict,
    current_eval: dict,
    follow_ups: Optional[list],
) -> Dict[str, Any]:
    """Save Q&A transcript + evaluation block; append evaluation to in-memory list."""
    qa_entry = AnswerEvaluator.build_qa_entry(
        question_obj, current_q, transcript, follow_ups
    )
    await api_client.save_transcript(qa_entry)

    evaluation = AnswerEvaluator.build_evaluation_block(
        question_obj,
        current_q,
        transcript,
        primary_eval,
        current_eval,
        follow_ups,
    )
    analysis_evaluations.append(evaluation)
    await api_client.save_evaluation(evaluation)
    return evaluation


async def persist_interview_close(
    api_client: SessionApiClient,
    evaluations: List[Dict[str, Any]],
    transcript_log: List[Dict[str, Any]],
) -> None:
    """Persist final summary and full conversational transcript."""
    await api_client.save_final_summary(evaluations)
    await api_client.save_interview_metadata(transcript_log)
