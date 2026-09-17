"""Persist screening transcripts and evaluations for interview sessions."""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from src.models.application import Application
from src.models.enums import InterviewType, TimelineActorType, TimelineEventType
from src.models.interview_analysis import InterviewAnalysis
from src.models.interview_session import InterviewSession
from src.schemas.interview_analysis import (
    InterviewAnalysisResponse,
    SaveEvaluationRequest,
    SaveEvaluationSummaryRequest,
    SaveQaTranscriptRequest,
    SaveTranscriptRequest,
)
from src.services.application_timeline_service import (
    append_timeline_event,
    timeline_event_types,
)

__all__ = [
    "get_analysis_for_session",
    "analysis_to_response",
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


def _planned_question_count(raw: Any) -> int:
    if isinstance(raw, list):
        return len(raw)
    if isinstance(raw, dict):
        questions = raw.get("questions")
        if isinstance(questions, list):
            return len(questions)
    return 0


def _conversation_transcript(session: InterviewSession) -> list[Any]:
    meta = session.interview_metadata if isinstance(session.interview_metadata, dict) else {}
    transcript = meta.get("conversation_transcript")
    if isinstance(transcript, list):
        return transcript
    return []


def _gmeet_link(session: InterviewSession) -> str | None:
    meta = session.interview_metadata if isinstance(session.interview_metadata, dict) else {}
    link = meta.get("gmeet_link")
    return link if isinstance(link, str) and link.strip() else None


def get_analysis_for_session(
    db: Session,
    session_id: UUID,
) -> tuple[InterviewSession, InterviewAnalysis] | None:
    stmt = (
        select(InterviewSession)
        .options(selectinload(InterviewSession.analysis))
        .where(InterviewSession.id == session_id)
    )
    session = db.scalar(stmt)
    if session is None or session.analysis is None:
        return None
    return session, session.analysis


def analysis_to_response(
    session: InterviewSession,
    analysis: InterviewAnalysis,
) -> InterviewAnalysisResponse:
    interview_type = (
        analysis.interview_type.value
        if analysis.interview_type is not None
        else (
            session.interview_type.value
            if session.interview_type is not None
            else None
        )
    )
    return InterviewAnalysisResponse(
        id=analysis.id,
        interview_session_id=analysis.interview_session_id,
        application_id=analysis.application_id,
        interview_type=interview_type,
        recording_url=analysis.recording_url,
        analysis_result=analysis.analysis_result,
        question_answer=analysis.question_answer,
        conversation_transcript=_conversation_transcript(session),
        session_status=session.status.value,
        scheduled_at=session.scheduled_at,
        completed_at=session.completed_at,
        gmeet_link=_gmeet_link(session),
        questions_planned=_planned_question_count(session.generated_questions),
        created_at=analysis.created_at,
    )


def _emit_analysis_ready(
    db: Session,
    session: InterviewSession,
    analysis: InterviewAnalysis,
    summary: dict[str, Any],
) -> None:
    types = timeline_event_types(db, session.application_id)
    if TimelineEventType.analysis_ready.value in types:
        return

    application = session.application
    if application is None:
        application = db.get(Application, session.application_id)
    if application is None:
        return

    overall = summary.get("overall_score")
    append_timeline_event(
        db,
        application=application,
        event_type=TimelineEventType.analysis_ready,
        actor_type=TimelineActorType.system,
        to_status=application.status,
        metadata={
            "interview_session_id": str(session.id),
            "interview_analysis_id": str(analysis.id),
            "overall_score": overall,
        },
    )


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
    summary = body.model_dump(mode="json")
    result["final_summary"] = summary
    analysis.analysis_result = result
    db.add(analysis)
    _emit_analysis_ready(db, session, analysis, summary)
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
