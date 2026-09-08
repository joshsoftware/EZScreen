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


def _as_text(value: Any) -> str:
    """Return a schema-safe transcript text value."""
    return str(value).strip() if value is not None else ""


def _normalize_follow_ups(follow_ups: Any) -> list[dict[str, str]]:
    """Convert orchestrator follow-up fields to the Core API transcript schema."""
    if not isinstance(follow_ups, list):
        return []

    normalized = []
    for follow_up in follow_ups:
        if not isinstance(follow_up, dict):
            continue
        bot_speech = _as_text(
            follow_up.get("bot_speech", follow_up.get("ai_response"))
        )
        if not bot_speech:
            continue
        normalized.append(
            {
                "interaction_type": _as_text(follow_up.get("interaction_type"))
                or "follow_up",
                "bot_speech": bot_speech,
                "candidate_answer": _as_text(
                    follow_up.get("candidate_answer", follow_up.get("candidate_speech"))
                ),
            }
        )
    return normalized


def normalize_interview_metadata(transcript_log: List[Dict[str, Any]]) -> list[dict[str, Any]]:
    """Build a Core API-compatible final transcript from internal interview events."""
    normalized: list[dict[str, Any]] = []

    for interaction in transcript_log:
        if not isinstance(interaction, dict):
            continue

        bot_speech = _as_text(interaction.get("bot_speech"))
        if not bot_speech:
            continue

        item: dict[str, Any] = {
            "interaction_type": _as_text(interaction.get("interaction_type"))
            or "conversation",
            "bot_speech": bot_speech,
            "candidate_answer": _as_text(interaction.get("candidate_answer")),
            "follow_ups": _normalize_follow_ups(interaction.get("follow_ups")),
        }
        question_id = interaction.get("question_id")
        if isinstance(question_id, int) and not isinstance(question_id, bool) and question_id >= 1:
            item["question_id"] = question_id
        normalized.append(item)

        # These are tracked separately by the orchestrator but are persisted as
        # regular transcript interactions so they satisfy Core API validation.
        for turn in interaction.get("conversational_turns", []):
            if not isinstance(turn, dict):
                continue
            response = _as_text(turn.get("ai_response"))
            if response:
                normalized.append(
                    {
                        "interaction_type": "conversational",
                        "bot_speech": response,
                        "candidate_answer": _as_text(turn.get("candidate_speech")),
                        "follow_ups": [],
                    }
                )

        for prompt in interaction.get("silence_prompts", []):
            if not isinstance(prompt, dict):
                continue
            prompt_text = _as_text(prompt.get("bot_speech"))
            if prompt_text:
                normalized.append(
                    {
                        "interaction_type": "silence_prompt",
                        "bot_speech": prompt_text,
                        "candidate_answer": _as_text(prompt.get("candidate_reply")),
                        "follow_ups": [],
                    }
                )

    return normalized


class SessionApiClient:
    """Handles all core-api HTTP calls for a specific interview session."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.base_url = settings.core_api_url.rstrip("/")

    async def save_transcript(self, qa_entry: Dict[str, Any]) -> bool:
        """Appends a single Q&A entry to the question_answer column."""
        logger.info("Saving transcript to core-api", extra={
            "session_id": self.session_id,
            "question_id": qa_entry.get("question_id")
        })
        logger.debug("Transcript payload", extra={"payload": json.dumps(qa_entry, indent=2)})

        try:
            url = f"{self.base_url}/api/v1/interview-sessions/{self.session_id}/qa-transcript"
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(url, json=qa_entry)
                if resp.status_code not in (200, 201, 204):
                    logger.error(
                        "Failed to save transcript",
                        extra={"status": resp.status_code, "response": resp.text},
                    )
                    return False
                return True
        except Exception as err:
            logger.error("Error saving transcript to core-api", extra={"error": str(err)})
            return False

    async def save_evaluation(self, evaluation: Dict[str, Any]) -> bool:
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
                resp = await client.post(url, json=evaluation)
                if resp.status_code not in (200, 201, 204):
                    logger.error(
                        "Failed to save evaluation",
                        extra={"status": resp.status_code, "response": resp.text},
                    )
                    return False
                return True
        except Exception as err:
            logger.error("Error saving evaluation to core-api", extra={"error": str(err)})
            return False

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
                resp = await client.post(url, json=final_summary)
                if resp.status_code not in (200, 201, 204):
                    logger.error("Failed to save final summary", extra={"status": resp.status_code})
        except Exception as err:
            logger.error("Error saving final summary to core-api", extra={"error": str(err)})

    async def save_interview_metadata(self, transcript_log: List[Dict[str, Any]]):
        """Saves the full conversational transcript (greetings, small talk, QA) to interview_metadata."""
        transcript_payload = normalize_interview_metadata(transcript_log)
        logger.info("Saving full interview metadata to core-api", extra={
            "session_id": self.session_id,
            "total_interactions": len(transcript_payload)
        })
        
        try:
            url = f"{self.base_url}/api/v1/interview-sessions/{self.session_id}/transcript"
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(
                    url,
                    json={"interview_metadata": transcript_payload},
                )
                if resp.status_code not in (200, 201, 204):
                    logger.error(
                        "Failed to save interview metadata",
                        extra={"status": resp.status_code, "response": resp.text},
                    )
        except Exception as err:
            logger.error("Error saving interview metadata to core-api", extra={"error": str(err)})
