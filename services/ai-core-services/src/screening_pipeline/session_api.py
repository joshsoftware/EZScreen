"""
Core API Client for persisting interview data.
Handles all HTTP communication with the core-api service.
"""
import json
import httpx
from typing import Dict, Any, List
from src.core.config import settings
from src.core.logger import logger
from src.screening_pipeline.prompts import RECOMMENDATION_THRESHOLD


class SessionApiClient:
    """Handles all core-api HTTP calls for a specific interview session."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.base_url = settings.core_api_url.rstrip("/")

    async def save_transcript(self, qa_entry: Dict[str, Any]):
        """Appends a single Q&A entry to the question_answer column."""
        logger.info("Saving transcript to core-api", extra={
            "session_id": self.session_id,
            "question_id": qa_entry.get("question_id")
        })
        logger.debug("Transcript payload", extra={"payload": json.dumps(qa_entry, indent=2)})

        try:
            url = f"{self.base_url}/api/v1/interview-sessions/{self.session_id}/transcript"
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(url, json=qa_entry)
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
                resp = await client.post(url, json=evaluation)
                if resp.status_code not in (200, 201, 204):
                    logger.error("Failed to save evaluation", extra={"status": resp.status_code})
        except Exception as err:
            logger.error("Error saving evaluation to core-api", extra={"error": str(err)})

    async def save_final_summary(self, evaluations: List[Dict[str, Any]]):
        """Calculates the final_summary from all evaluations and sends it to core-api."""
        total_questions = len(evaluations)
        if total_questions == 0:
            return

        # Topic Score Resolution (AI_PROCESSING.md Section 5.4)
        total_score = 0.0
        for ev in evaluations:
            primary_score = ev.get("score", 0)
            follow_ups = ev.get("follow_ups", [])
            if follow_ups and follow_ups[0].get("score") is not None:
                topic_score = (primary_score + follow_ups[0]["score"]) / 2
            else:
                topic_score = primary_score
            total_score += topic_score

        max_possible_score = total_questions * 10
        overall_score = round((total_score / max_possible_score) * 10, 1)

        if overall_score >= RECOMMENDATION_THRESHOLD:
            final_recommendation = "shortlist_for_l1"
        else:
            final_recommendation = "reject"

        final_summary = {
            "total_score": total_score,
            "max_possible_score": max_possible_score,
            "overall_score": overall_score,
            "final_recommendation": final_recommendation
        }

        logger.info("Saving final summary to core-api", extra={
            "session_id": self.session_id,
            "overall_score": overall_score,
            "recommendation": final_recommendation
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
        logger.info("Saving full interview metadata to core-api", extra={
            "session_id": self.session_id,
            "total_interactions": len(transcript_log)
        })
        
        try:
            url = f"{self.base_url}/api/v1/interview-sessions/{self.session_id}/metadata"
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(url, json={"interview_metadata": transcript_log})
                if resp.status_code not in (200, 201, 204):
                    logger.error("Failed to save interview metadata", extra={"status": resp.status_code})
        except Exception as err:
            logger.error("Error saving interview metadata to core-api", extra={"error": str(err)})
