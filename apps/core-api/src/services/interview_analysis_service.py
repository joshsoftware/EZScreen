"""Persist screening transcripts and evaluations for interview sessions."""

from __future__ import annotations

import logging
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from src.config.settings import settings
from src.models.application import Application
from src.models.enums import InterviewType, TimelineActorType, TimelineEventType
from src.models.interview_analysis import InterviewAnalysis
from src.models.interview_session import InterviewSession
from src.schemas.interview_analysis import (
    CorrectedScreeningAnswer,
    InterviewAnalysisResponse,
    ReEvaluateScreeningRequest,
    SaveEvaluationRequest,
    SaveEvaluationSummaryRequest,
    SaveQaTranscriptRequest,
    SaveTranscriptRequest,
)
from src.services.application_timeline_service import (
    append_timeline_event,
    timeline_event_types,
)
from src.services.storage_service import create_presigned_recording_url

__all__ = [
    "get_analysis_for_session",
    "analysis_to_response",
    "save_qa_transcript",
    "save_evaluation",
    "save_evaluation_summary",
    "save_conversation_transcript",
    "re_evaluate_screening",
    "ScreeningReEvaluationError",
]

logger = logging.getLogger(__name__)


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


def _score(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _replaces_scored_summary_with_empty(
    analysis_result: dict[str, Any],
    incoming: dict[str, Any],
) -> bool:
    """True when a zero "nothing was scored" summary would overwrite a real
    one while scored answers exist. A legitimately all-zero interview still
    saves: there the stored summary is zero too (or absent)."""
    if _score(incoming.get("total_score")) > 0 or _score(incoming.get("overall_score")) > 0:
        return False
    if not _evaluations_list(analysis_result):
        return False
    existing = analysis_result.get("final_summary")
    if not isinstance(existing, dict):
        return False
    return _score(existing.get("total_score")) > 0 or _score(existing.get("overall_score")) > 0


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


def _recording_playback_url(stored: str | None) -> str | None:
    """interview_analysis.recording_url holds a MinIO key; hand the browser a
    fresh presigned URL. Values that are already URLs are passed through."""
    if not stored:
        return None
    if stored.startswith(("http://", "https://")):
        return stored
    return create_presigned_recording_url(stored)


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
        recording_url=_recording_playback_url(analysis.recording_url),
        analysis_result=analysis.analysis_result,
        question_answer=analysis.question_answer,
        conversation_transcript=_conversation_transcript(session),
        session_status=session.status.value,
        scheduled_at=session.scheduled_at,
        completed_at=session.completed_at,
        gmeet_link=_gmeet_link(session),
        questions_planned=_planned_question_count(session.generated_questions),
        re_evaluations=_re_evaluation_history(analysis.analysis_result),
        created_at=analysis.created_at,
    )


def _re_evaluation_history(raw: Any) -> list[dict[str, Any]]:
    history = raw.get("re_evaluations") if isinstance(raw, dict) else None
    return [item for item in history if isinstance(item, dict)] if isinstance(history, list) else []


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
    if _replaces_scored_summary_with_empty(result, summary):
        # A second bot runtime that never heard the candidate saved "no
        # answers were scored" (0.0) over the real summary (Bugs 44-46).
        logger.warning(
            "Ignored an empty screening summary over a scored one",
            extra={"interview_session_id": str(session.id)},
        )
        return
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


_RE_EVALUATION_TIMEOUT_SECONDS = 180.0


class ScreeningReEvaluationError(RuntimeError):
    """ai-core could not re-score the answers; nothing was changed."""


def _apply_corrections(
    evaluations: list[dict[str, Any]],
    corrections: list[CorrectedScreeningAnswer],
) -> list[int]:
    """Write HR's corrected answers into the evaluations; return edited question ids."""
    by_id = {item.get("question_id"): item for item in evaluations}
    edited: list[int] = []
    for correction in corrections:
        item = by_id.get(correction.question_id)
        if item is None:
            raise ValueError(f"Question {correction.question_id} was not evaluated in this screening")
        changed = False
        if (
            correction.candidate_answer is not None
            and correction.candidate_answer.strip() != str(item.get("candidate_answer") or "").strip()
        ):
            item["candidate_answer"] = correction.candidate_answer.strip()
            changed = True
        follow_ups = item.get("follow_ups") if isinstance(item.get("follow_ups"), list) else []
        for index, answer in enumerate(correction.follow_up_answers or []):
            if answer is None or index >= len(follow_ups) or not isinstance(follow_ups[index], dict):
                continue
            if answer.strip() != str(follow_ups[index].get("follow_up_answer") or "").strip():
                follow_ups[index]["follow_up_answer"] = answer.strip()
                changed = True
        if changed:
            edited.append(correction.question_id)
    return edited


def re_evaluate_screening(
    db: Session,
    session: InterviewSession,
    analysis: InterviewAnalysis,
    body: ReEvaluateScreeningRequest,
    *,
    actor_id: UUID,
    actor_name: str | None = None,
) -> InterviewAnalysis:
    """Re-score the saved answers (after HR corrections) the way the live bot
    scores them, and replace the evaluations and final summary.

    The first re-evaluation keeps the bot's original evaluations and summary;
    every run is recorded in analysis_result["re_evaluations"].
    """
    result = _analysis_result_dict(analysis.analysis_result)
    evaluations = deepcopy(_evaluations_list(result))
    if not evaluations:
        raise ValueError("This screening has no evaluated answers to re-score")
    edited = _apply_corrections(evaluations, body.answers)

    url = f"{settings.ai_services_base_url.rstrip('/')}/internal/v1/screening/re-evaluate"
    try:
        with httpx.Client(timeout=_RE_EVALUATION_TIMEOUT_SECONDS) as client:
            response = client.post(
                url,
                json={
                    "interview_session_id": str(session.id),
                    "evaluations": evaluations,
                    "generated_questions": session.generated_questions,
                },
            )
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.error(
            "Screening re-evaluation failed",
            extra={"interview_session_id": str(session.id), "error": str(exc)},
        )
        raise ScreeningReEvaluationError(
            "Re-evaluation failed: the AI service did not respond. Nothing was changed; try again."
        ) from exc

    new_evaluations = payload.get("evaluations") if isinstance(payload, dict) else None
    new_summary = payload.get("final_summary") if isinstance(payload, dict) else None
    if not isinstance(new_evaluations, list) or not isinstance(new_summary, dict):
        raise ScreeningReEvaluationError(
            "Re-evaluation failed: the AI service returned an invalid result. Nothing was changed."
        )

    previous_summary = result.get("final_summary") if isinstance(result.get("final_summary"), dict) else {}
    if "original" not in result:
        result["original"] = {
            "evaluations": _evaluations_list(result),
            "final_summary": previous_summary,
        }
    history = result.get("re_evaluations") if isinstance(result.get("re_evaluations"), list) else []
    history.append(
        {
            "at": datetime.now(timezone.utc).isoformat(),
            "by": str(actor_id),
            # Shown in the evaluation history; kept as of the re-evaluation.
            "by_name": actor_name,
            "previous_overall_score": previous_summary.get("overall_score"),
            "overall_score": new_summary.get("overall_score"),
            "edited_question_ids": edited,
        }
    )
    result["re_evaluations"] = history
    result["evaluations"] = new_evaluations
    result["final_summary"] = new_summary
    analysis.analysis_result = result
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return analysis
