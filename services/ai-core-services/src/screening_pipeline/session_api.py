"""
Core API Client for persisting interview data.
Handles all HTTP communication with the core-api service.
"""
import json
import httpx
from typing import Dict, Any, List
from src.core.config import settings
from src.core.logger import logger
from src.screening_pipeline.summary_calculator import compute_final_summary


def _normalize_interaction(interaction: Dict[str, Any]) -> Dict[str, Any]:
    """Reshape an in-memory transcript entry for the core-api transcript schema.

    The orchestrator records follow-ups as candidate_speech/ai_response, while
    core-api expects bot_speech/candidate_answer.
    """
    follow_ups: List[Dict[str, Any]] = []
    for turn in interaction.get("follow_ups") or []:
        bot_speech = turn.get("ai_response") or turn.get("bot_speech") or ""
        if not bot_speech:
            continue
        follow_ups.append(
            {
                "interaction_type": "follow_up",
                "bot_speech": bot_speech,
                "candidate_answer": turn.get("candidate_speech")
                or turn.get("candidate_answer")
                or "",
            }
        )

    normalized: Dict[str, Any] = {
        "interaction_type": interaction.get("interaction_type") or "question",
        "bot_speech": interaction.get("bot_speech") or "",
        "candidate_answer": interaction.get("candidate_answer") or "",
        "follow_ups": follow_ups,
    }

    question_id = interaction.get("question_id")
    if isinstance(question_id, int) and question_id >= 1:
        normalized["question_id"] = question_id

    return normalized


class SessionApiClient:
    """Handles all core-api HTTP calls for a specific interview session."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.base_url = settings.core_api_url.rstrip("/")
        self.headers: Dict[str, str] = {}
        if settings.internal_service_token:
            self.headers["X-Internal-Service-Token"] = settings.internal_service_token

    async def save_transcript(self, qa_entry: Dict[str, Any]):
        """Appends a single Q&A entry to the question_answer column."""
        logger.info("Saving transcript to core-api", extra={
            "session_id": self.session_id,
            "question_id": qa_entry.get("question_id")
        })
        logger.debug("Transcript payload", extra={"payload": json.dumps(qa_entry, indent=2)})

        try:
            url = f"{self.base_url}/api/v1/interview-sessions/{self.session_id}/qa-transcript"
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(url, json=qa_entry, headers=self.headers)
                if resp.status_code not in (200, 201, 204):
                    logger.error("Failed to save transcript", extra={"status": resp.status_code})
        except Exception as err:
            logger.error("Error saving transcript to core-api", extra={"error": str(err)})

    async def save_evaluation(self, evaluation: Dict[str, Any]):
        """Appends a single evaluation block to analysis_result.evaluations."""
        logger.info("Saving evaluation to core-api", extra={
            "session_id": self.session_id,
            "question_id": evaluation.get("question_id"),
            "score": evaluation.get("score"),
            "decision": evaluation.get("decision")
        })
        logger.debug("Evaluation payload", extra={"payload": json.dumps(evaluation, indent=2)})

        try:
            url = f"{self.base_url}/api/v1/interview-sessions/{self.session_id}/evaluation"
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(url, json=evaluation, headers=self.headers)
                if resp.status_code not in (200, 201, 204):
                    logger.error("Failed to save evaluation", extra={"status": resp.status_code})
        except Exception as err:
            logger.error("Error saving evaluation to core-api", extra={"error": str(err)})

    async def save_final_summary(self, evaluations: List[Dict[str, Any]]):
        """Calculates the final_summary from all evaluations and sends it to core-api."""
        final_summary = compute_final_summary(evaluations)
        if final_summary is None:
            return

        logger.info("Saving final summary to core-api", extra={
            "session_id": self.session_id,
            "overall_score": final_summary["overall_score"],
            "recommendation": final_summary["final_recommendation"]
        })

        try:
            url = f"{self.base_url}/api/v1/interview-sessions/{self.session_id}/evaluation/summary"
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(url, json=final_summary, headers=self.headers)
                if resp.status_code not in (200, 201, 204):
                    logger.error("Failed to save final summary", extra={"status": resp.status_code})
        except Exception as err:
            logger.error("Error saving final summary to core-api", extra={"error": str(err)})

    async def save_interview_metadata(self, transcript_log: List[Dict[str, Any]]):
        """Saves the full conversational transcript (greetings, small talk, QA) to interview_metadata."""
        # core-api rejects interactions without bot speech, which would fail the whole payload.
        interactions = [
            item
            for item in (_normalize_interaction(entry) for entry in transcript_log)
            if item["bot_speech"]
        ]
        if not interactions:
            logger.warning("Skipping interview metadata save, no usable interactions", extra={
                "session_id": self.session_id
            })
            return

        logger.info("Saving full interview metadata to core-api", extra={
            "session_id": self.session_id,
            "total_interactions": len(interactions)
        })

        try:
            url = f"{self.base_url}/api/v1/interview-sessions/{self.session_id}/transcript"
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(
                    url, json={"interview_metadata": interactions}, headers=self.headers
                )
                if resp.status_code not in (200, 201, 204):
                    logger.error("Failed to save interview metadata", extra={"status": resp.status_code})
        except Exception as err:
            logger.error("Error saving interview metadata to core-api", extra={"error": str(err)})
