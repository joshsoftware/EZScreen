"""
Interview Orchestrator — Main state machine for the AI screening interview.
Controls the flow: Greeting → Questions → Evaluation → Follow-up → Closing.
"""

from __future__ import annotations

import asyncio
import random
from typing import TYPE_CHECKING, Any, Optional

from src.core.config import settings
from src.core.logger import logger
from src.llm.client import OllamaClient
from src.meeting_bot.repository import interview_session_repo
from src.screening_pipeline.evaluator import AnswerEvaluator
from src.screening_pipeline.persistence import (
    persist_completed_question,
    persist_interview_close,
)
from src.screening_pipeline.prompts import (
    CLOSING_TEXT,
    GREETING_TEXT,
    MAX_FOLLOW_UPS_PER_QUESTION,
)
from src.screening_pipeline.session_api import SessionApiClient
from src.screening_pipeline.speech_filter import is_probable_hallucination
from src.screening_pipeline.tts_client import LocalKokoroTTSClient

if TYPE_CHECKING:
    from src.screening_pipeline.stt_client import WhisperCloudSTTClient


class InterviewOrchestrator:
    """
    Manages the state machine for the AI interview.
    Coordinates STT, Intent Router, LLM Evaluator, TTS, and Core-API persistence.
    """

    def __init__(
        self,
        session_id: str,
        websocket,
        *,
        stt_client: Optional[WhisperCloudSTTClient] = None,
        tts_client: Optional[LocalKokoroTTSClient] = None,
        evaluator: Optional[AnswerEvaluator] = None,
        llm_client: Optional[OllamaClient] = None,
        api_client: Optional[SessionApiClient] = None,
    ):
        self.session_id = session_id
        self.websocket = websocket
        self.session: Any = None
        self.questions: list = []
        self.current_question_idx = 0
        self.is_active = False

        if stt_client is not None:
            self.stt_client = stt_client
        else:
            from src.screening_pipeline.stt_client import WhisperCloudSTTClient as _STT

            self.stt_client = _STT(
                api_url=settings.whisper_api_url,
                api_key=settings.whisper_api_key,
                on_transcript=self.handle_candidate_speech,
            )
        self.tts_client = tts_client or LocalKokoroTTSClient()

        resolved_llm = llm_client or OllamaClient()
        self.evaluator = evaluator or AnswerEvaluator(resolved_llm)
        self.api_client = api_client  # Usually set after session load

        self.current_interaction_state = "idle"  # idle, speaking, listening, evaluating
        self.transcript_log: list = []
        self.analysis_evaluations: list = []

    # ──────────────────────────── LIFECYCLE ────────────────────────────

    async def start(self):
        """Initializes the interview session and speaks the greeting."""
        logger.info("Orchestrator starting", extra={"session_id": self.session_id})

        # Path param is interview_session_id (bot_id unknown when WS URL is built).
        self.session = await interview_session_repo.get_by_id(self.session_id)

        if not self.session:
            logger.error(
                "No session found for bot. Cannot start interview.",
                extra={"session_id": self.session_id},
            )
            return

        if self.api_client is None:
            self.api_client = SessionApiClient(session_id=str(self.session.id))

        self.questions = self.session.generated_questions or []
        random.shuffle(self.questions)
        self.is_active = True

        await self.stt_client.connect()

        self.transcript_log.append(
            {
                "interaction_type": "greeting",
                "bot_speech": GREETING_TEXT,
                "candidate_answer": "",
            }
        )
        await self.speak(GREETING_TEXT)
        self.current_interaction_state = "listening"

    async def cleanup(self):
        """Teardown connections."""
        self.is_active = False
        await self.stt_client.close()

    # ──────────────────────────── STT CALLBACK ────────────────────────────

    def handle_candidate_speech(self, transcript: str):
        """Callback from STT when the candidate finishes speaking."""
        if not self.is_active or self.current_interaction_state != "listening":
            return

        if is_probable_hallucination(transcript):
            logger.info(
                "Ignored probable Whisper hallucination or noise",
                extra={"transcript": transcript},
            )
            return

        logger.info("Candidate speech received", extra={"transcript": transcript})
        self.current_interaction_state = "evaluating"
        asyncio.create_task(self._process_speech(transcript))

    # ──────────────────────────── MAIN PROCESSING ────────────────────────────

    async def _process_speech(self, transcript: str):
        """Routes the candidate's speech through intent detection and evaluation."""
        if self.transcript_log and self.transcript_log[-1].get("interaction_type") == "greeting":
            self.transcript_log[-1]["candidate_answer"] = transcript
            await self._ask_next_question()
            return

        question_obj = self.questions[self.current_question_idx]
        current_q = question_obj.get("question", "")

        intent, ai_response = await self.evaluator.route_intent(current_q, transcript)

        if intent in ["CLARIFICATION", "SMALL_TALK"]:
            await self._handle_conversational(transcript, ai_response)
            return

        if intent == "SKIP":
            await self._handle_skip(question_obj, current_q, transcript)
            return

        await self._handle_answer(question_obj, current_q, transcript)

    # ──────────────────────────── INTENT HANDLERS ────────────────────────────

    async def _handle_conversational(self, transcript: str, ai_response: str):
        """Handles CLARIFICATION and SMALL_TALK intents."""
        if not ai_response.strip():
            ai_response = "Okay, sounds good."

        if self.transcript_log:
            self.transcript_log[-1].setdefault("follow_ups", []).append(
                {
                    "candidate_speech": transcript,
                    "ai_response": ai_response,
                }
            )

        await self.speak(ai_response)
        self.current_interaction_state = "listening"

    async def _handle_skip(self, question_obj: dict, current_q: str, transcript: str):
        """Handles SKIP intent — saves 0-score evaluation and moves on."""
        if self.transcript_log:
            self.transcript_log[-1]["candidate_answer"] = transcript

        qa_entry = AnswerEvaluator.build_qa_entry(question_obj, current_q, transcript)
        await self.api_client.save_transcript(qa_entry)

        skip_eval = AnswerEvaluator.build_skip_evaluation(question_obj, transcript)
        self.analysis_evaluations.append(skip_eval)
        await self.api_client.save_evaluation(skip_eval)

        self.current_question_idx += 1
        await self._ask_next_question()

    async def _handle_answer(self, question_obj: dict, current_q: str, transcript: str):
        """Handles ANSWERING intent — evaluates and decides follow-up or next question."""
        primary_eval_data = None
        if self.transcript_log and self.transcript_log[-1].get("primary_eval"):
            primary_eval_data = self.transcript_log[-1]["primary_eval"]
            expected_keywords = ", ".join(primary_eval_data.get("keywords_missing", []))
            answer_depth = "partial_depth"
        else:
            expected_keywords = ", ".join(question_obj.get("expected_keywords", []))
            answer_depth = question_obj.get("answer_depth", "partial_depth")

        follow_up_context = None
        if self.transcript_log and self.transcript_log[-1].get("follow_ups"):
            follow_up_context = self.transcript_log[-1]["follow_ups"]

        eval_data = await self.evaluator.evaluate_answer(
            current_question=current_q,
            transcript=transcript,
            expected_keywords=expected_keywords,
            answer_depth=answer_depth,
            follow_up_context=follow_up_context,
        )

        decision = eval_data.get("decision", "NEXT_QUESTION")
        is_complete = decision == "NEXT_QUESTION"
        follow_up_question = eval_data.get("suggested_follow_up", "")

        if decision == "REPEAT_QUESTION":
            is_complete = False
            follow_up_question = "I'm sorry, could you please repeat your answer?"

        current_follow_ups = (
            self.transcript_log[-1].get("follow_ups", []) if self.transcript_log else []
        )
        if len(current_follow_ups) >= MAX_FOLLOW_UPS_PER_QUESTION and not is_complete:
            logger.info("Follow-up limit reached, forcing completion")
            is_complete = True
            follow_up_question = ""
            eval_data["decision"] = "NEXT_QUESTION"

        if not is_complete and follow_up_question:
            if self.transcript_log:
                self.transcript_log[-1]["primary_eval"] = eval_data
                self.transcript_log[-1].setdefault("follow_ups", []).append(
                    {
                        "candidate_speech": transcript,
                        "ai_response": follow_up_question,
                    }
                )
            await self.speak(follow_up_question)
            self.current_interaction_state = "listening"
        else:
            await self._complete_question(
                question_obj, current_q, transcript, primary_eval_data, eval_data
            )

    async def _complete_question(
        self,
        question_obj: dict,
        current_q: str,
        transcript: str,
        primary_eval: dict,
        current_eval: dict,
    ):
        """Saves the completed question's transcript and evaluation to core-api."""
        if self.transcript_log:
            self.transcript_log[-1]["candidate_answer"] = transcript

        follow_ups = self.transcript_log[-1].get("follow_ups") if self.transcript_log else None

        await persist_completed_question(
            self.api_client,
            self.analysis_evaluations,
            question_obj=question_obj,
            current_q=current_q,
            transcript=transcript,
            primary_eval=primary_eval,
            current_eval=current_eval,
            follow_ups=follow_ups,
        )

        self.current_question_idx += 1
        await self._ask_next_question()

    # ──────────────────────────── QUESTION FLOW ────────────────────────────

    async def _ask_next_question(self):
        """Moves to the next question or closes the interview."""
        if self.current_question_idx >= len(self.questions):
            await self._close_interview()
            return

        question_obj = self.questions[self.current_question_idx]
        q_text = question_obj.get("question", "")

        self.transcript_log.append(
            {
                "interaction_type": "question",
                "question_id": question_obj.get("id"),
                "bot_speech": q_text,
                "candidate_answer": "",
                "follow_ups": [],
            }
        )

        await self.speak(q_text)
        self.current_interaction_state = "listening"

    async def _close_interview(self):
        """Speaks closing message and saves the final summary."""
        self.transcript_log.append(
            {
                "interaction_type": "closing",
                "bot_speech": CLOSING_TEXT,
                "candidate_answer": "",
            }
        )

        await persist_interview_close(
            self.api_client,
            self.analysis_evaluations,
            self.transcript_log,
        )

        await self.speak(CLOSING_TEXT)
        self.current_interaction_state = "closing"

    # ──────────────────────────── TTS ────────────────────────────

    async def speak(self, text: str):
        """Synthesizes text via TTS and streams audio to the WebSocket."""
        logger.info("AI speaking", extra={"text": text[:80]})
        self.current_interaction_state = "speaking"
        from src.screening_pipeline.audio_websocket import speak_to_attendee

        async for chunk in self.tts_client.synthesize(text):
            if not self.is_active:
                break
            await speak_to_attendee(self.websocket, chunk)
