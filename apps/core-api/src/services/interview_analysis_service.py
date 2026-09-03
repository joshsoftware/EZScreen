"""Persist screening transcripts and evaluations for interview sessions."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from sqlalchemy.orm import Session

from src.models.enums import InterviewType
from src.models.interview_analysis import InterviewAnalysis
from src.models.interview_session import InterviewSession
from src.schemas.interview_analysis import (
    SaveEvaluationRequest,
    SaveEvaluationSummaryRequest,
    SaveQaTranscriptRequest,
    SaveTranscriptRequest,
)

__all__ = [
    "save_qa_transcript",
    "save_evaluation",
    "save_evaluation_summary",
    "save_conversation_transcript",
]


def _question_answer_list(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    return []


def _analysis_result_dict(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return deepcopy(raw)
    return {}


def _evaluations_list(analysis_result: dict[str, Any]) -> list[dict[str, Any]]:
    evaluations = analysis_result.get("evaluations")
    if isinstance(evaluations, list):
        return [item for item in evaluations if isinstance(item, dict)]
    return []


def _upsert_by_question_id(
    items: list[dict[str, Any]],
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    question_id = payload.get("question_id")
    updated = False
    for index, item in enumerate(items):
        if item.get("question_id") == question_id:
            items[index] = {**item, **payload}
            updated = True
            break
    if not updated:
        items.append(payload)
    return items


def _get_or_create_analysis(
    db: Session,
    session: InterviewSession,
) -> InterviewAnalysis:
    existing = session.analysis
    if existing is not None:
        return existing

    analysis = InterviewAnalysis(
        interview_session_id=session.id,
        application_id=session.application_id,
        interview_type=session.interview_type or InterviewType.screening_ai,
        question_answer=[],
        analysis_result={"evaluations": []},
    )
    db.add(analysis)
    db.flush()
    return analysis


def save_qa_transcript(
    db: Session,
    session: InterviewSession,
    body: SaveQaTranscriptRequest,
) -> None:
    analysis = _get_or_create_analysis(db, session)
    items = _question_answer_list(analysis.question_answer)
    payload = body.model_dump(mode="json")
    analysis.question_answer = _upsert_by_question_id(items, payload)
    db.add(analysis)
    db.commit()


def save_evaluation(
    db: Session,
    session: InterviewSession,
    body: SaveEvaluationRequest,
) -> None:
    analysis = _get_or_create_analysis(db, session)
    result = _analysis_result_dict(analysis.analysis_result)
    evaluations = _evaluations_list(result)
    payload = body.model_dump(mode="json")
    result["evaluations"] = _upsert_by_question_id(evaluations, payload)
    analysis.analysis_result = result
    db.add(analysis)
    db.commit()


def save_evaluation_summary(
    db: Session,
    session: InterviewSession,
    body: SaveEvaluationSummaryRequest,
) -> None:
    analysis = _get_or_create_analysis(db, session)
    result = _analysis_result_dict(analysis.analysis_result)
    result["final_summary"] = body.model_dump(mode="json")
    analysis.analysis_result = result
    db.add(analysis)
    db.commit()


def save_conversation_transcript(
    db: Session,
    session: InterviewSession,
    body: SaveTranscriptRequest,
) -> None:
    metadata = (
        deepcopy(session.interview_metadata)
        if isinstance(session.interview_metadata, dict)
        else {}
    )
    metadata["conversation_transcript"] = [
        item.model_dump(mode="json") for item in body.interview_metadata
    ]
    session.interview_metadata = metadata
    db.add(session)
    db.commit()
