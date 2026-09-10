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
from src.meeting_bot.client import bot_client
from src.meeting_bot.repository import interview_session_repo
from src.screening_pipeline.evaluator import AnswerEvaluator
from src.screening_pipeline.persistence import (
    persist_completed_question,
    persist_interview_close,
)
from src.screening_pipeline.prompts import (
    CLOSING_REPLY_TIMEOUT_SECONDS,
    CLOSING_TEXT,
    GREETING_TEXT,
    MAX_FOLLOW_UPS_PER_QUESTION,
    MAX_SILENCE_PROMPTS,
    SILENCE_PROMPT_CYCLE_GRACE_SECONDS,
    SILENCE_PROMPT_SECONDS,
    SILENCE_PROMPT_TEXT,
)
from src.screening_pipeline.session_api import SessionApiClient
from src.screening_pipeline.speech_filter import is_probable_hallucination
from src.screening_pipeline.tts_client import LocalKokoroTTSClient

if TYPE_CHECKING:
    from src.screening_pipeline.stt_client import WhisperCloudSTTClient


def _coerce_questions_list(raw: Any) -> list[dict]:
    """Normalize session.generated_questions to a list of question dicts."""
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict):
        nested = raw.get("questions")
        items = nested if isinstance(nested, list) else []
    else:
        items = []
    return [item for item in items if isinstance(item, dict) and item.get("question")]


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
        self.is_finalized = False
        self._silence_prompt_task: Optional[asyncio.Task] = None
        self._closing_reply_timeout_task: Optional[asyncio.Task] = None
        self._awaiting_silence_reply = False
        self._silence_prompt_count = 0
        self._silence_cycle_started_at: Optional[float] = None

        self.stt_client.on_speech_start = self.handle_candidate_activity

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

        self.questions = _coerce_questions_list(self.session.generated_questions)
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
        self._begin_listening()

    async def finalize(self, *, reason: str) -> None:
        """
        Persist the final summary and conversational transcript exactly once.

        Called on the normal closing path and again from cleanup(), so an interview
        that ends early (bot leaves, candidate hangs up, WebSocket drops) is still
        persisted. Never raises: teardown must not be blocked by a failed callback.
        """
        if self.is_finalized:
            return
        if self.api_client is None:
            logger.warning(
                "Skipping interview finalize, session was never loaded",
                extra={"session_id": self.session_id, "reason": reason},
            )
            return

        self.is_finalized = True
        logger.info(
            "Finalizing interview",
            extra={
                "session_id": self.session_id,
                "reason": reason,
                "evaluations": len(self.analysis_evaluations),
                "interactions": len(self.transcript_log),
            },
        )
        try:
            await persist_interview_close(
                self.api_client,
                self.llm_client,
                self.analysis_evaluations,
                self.transcript_log,
            )
        except Exception as err:
            logger.error(
                "Failed to finalize interview",
                extra={"session_id": self.session_id, "reason": reason, "error": str(err)},
            )

    async def cleanup(self):
        """Teardown connections, persisting the interview first if it ended early."""
        self.is_active = False
        self._cancel_silence_prompt()
        self._cancel_closing_reply_timeout()
        await self.finalize(reason="session_ended")
        await self.stt_client.close()

    # ──────────────────────────── STT CALLBACK ────────────────────────────

    def handle_candidate_speech(self, transcript: str):
        """Callback from STT when the candidate finishes speaking."""
        self._cancel_silence_prompt(reason="candidate transcript received")
        if self.current_interaction_state == "closing":
            self._cancel_closing_reply_timeout(reason="closing reply transcript received")
        if not self.is_active or self.current_interaction_state not in {"listening", "closing"}:
            return

        is_closing_reply = (
            self.current_interaction_state == "closing"
            and bool(self.transcript_log)
            and self.transcript_log[-1].get("interaction_type") == "closing"
        )
        if is_probable_hallucination(transcript) and not is_closing_reply:
            logger.info(
                "Ignored probable Whisper hallucination or noise",
                extra={"transcript": transcript},
            )
            return

        self._record_silence_reply(transcript)
        logger.info("Candidate speech received", extra={"transcript": transcript})
        self.current_interaction_state = "evaluating"
        asyncio.create_task(self._process_speech(transcript))

    def handle_candidate_activity(self):
        """Cancel the inactivity prompt as soon as VAD hears candidate speech."""
        self._cancel_silence_prompt(reason="candidate speech detected by VAD")
        if self.current_interaction_state == "closing":
            self._cancel_closing_reply_timeout(reason="closing reply detected by VAD")

    def _begin_listening(self):
        """Enter an eligible listening turn and start its silence-prompt cycle."""
        self.current_interaction_state = "listening"
        self._cancel_silence_prompt(reason="new listening turn")
        self._silence_prompt_count = 0
        self._silence_cycle_started_at = asyncio.get_running_loop().time()
        self._awaiting_silence_reply = False
        self._silence_prompt_task = asyncio.create_task(self._prompt_after_silence())
        logger.info(
            "Started 30-second candidate inactivity timer",
            extra={"session_id": self.session_id},
        )

    def _cancel_silence_prompt(self, *, reason: str = "session cleanup"):
        """Stop a pending inactivity prompt, if any."""
        task = self._silence_prompt_task
        if task and not task.done() and task is not asyncio.current_task():
            task.cancel()
            logger.info(
                "Cancelled candidate inactivity timer",
                extra={"session_id": self.session_id, "reason": reason},
            )
        self._silence_prompt_task = None

    def _cancel_closing_reply_timeout(self, *, reason: str = "session cleanup"):
        """Stop the silent closing-reply timeout, if it is pending."""
        task = self._closing_reply_timeout_task
        if task and not task.done() and task is not asyncio.current_task():
            task.cancel()
            logger.info(
                "Cancelled closing reply timeout",
                extra={"session_id": self.session_id, "reason": reason},
            )
        self._closing_reply_timeout_task = None

    def _record_silence_reply(self, transcript: str):
        """Attach the reply to the most recent "Are you there?" prompt."""
        if not self._awaiting_silence_reply:
            return

        self._awaiting_silence_reply = False
        if not self.transcript_log:
            return

        silence_prompts = self.transcript_log[-1].get("silence_prompts", [])
        if silence_prompts and isinstance(silence_prompts[-1], dict):
            silence_prompts[-1]["candidate_reply"] = transcript

    async def _prompt_after_silence(self):
        """Prompt up to three times, then close after continuous silence."""
        try:
            await asyncio.sleep(SILENCE_PROMPT_SECONDS)
        except asyncio.CancelledError:
            return

        if not self.is_active or self.current_interaction_state != "listening":
            return

        now = asyncio.get_running_loop().time()
        max_cycle_seconds = (
            SILENCE_PROMPT_SECONDS * MAX_SILENCE_PROMPTS
            + SILENCE_PROMPT_CYCLE_GRACE_SECONDS
        )
        if (
            self._silence_cycle_started_at is None
            or now - self._silence_cycle_started_at > max_cycle_seconds
        ):
            if self._silence_prompt_count:
                logger.warning(
                    "Silence prompt cycle exceeded its time window; restarting cycle",
                    extra={
                        "session_id": self.session_id,
                        "previous_attempts": self._silence_prompt_count,
                        "max_cycle_seconds": max_cycle_seconds,
                    },
                )
            self._silence_prompt_count = 0
            self._silence_cycle_started_at = now

        self._silence_prompt_count += 1
        logger.info(
            "Candidate inactive; sending silence prompt",
            extra={
                "session_id": self.session_id,
                "attempt": self._silence_prompt_count,
                "max_attempts": MAX_SILENCE_PROMPTS,
            },
        )
        if self.transcript_log:
            self.transcript_log[-1].setdefault("silence_prompts", []).append(
                {
                    "bot_speech": SILENCE_PROMPT_TEXT,
                    "candidate_reply": "",
                }
            )
        is_final_silence_prompt = self._silence_prompt_count >= MAX_SILENCE_PROMPTS
        if not is_final_silence_prompt:
            # Start the next 30-second interval now, rather than after the
            # short prompt finishes playing. This keeps the three prompts in
            # one continuous ~90-second silence window: 0:30, 1:00, 1:30.
            self._silence_prompt_task = asyncio.create_task(self._prompt_after_silence())

        self._awaiting_silence_reply = True
        await self.speak(SILENCE_PROMPT_TEXT)
        self.current_interaction_state = "listening"

        if is_final_silence_prompt:
            logger.info(
                "Silence prompt limit reached; closing interview",
                extra={"session_id": self.session_id, "attempts": self._silence_prompt_count},
            )
            self._silence_prompt_task = None
            self._awaiting_silence_reply = False
            self._silence_cycle_started_at = None
            await self._close_interview()
            return

        # Candidate VAD or transcript activity cancels the already-scheduled
        # next interval before another prompt can be sent.

    # ──────────────────────────── MAIN PROCESSING ────────────────────────────

    async def _process_speech(self, transcript: str):
        """Routes the candidate's speech through intent detection and evaluation."""
        if self.transcript_log and self.transcript_log[-1].get("interaction_type") == "closing":
            # The closing reply is conversational only. Persist it in the full
            # transcript before instructing the meeting bot to leave.
            self.transcript_log[-1]["candidate_answer"] = transcript
            await self._persist_closing_and_leave()
            return

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
        if not ai_response or not str(ai_response).strip():
            ai_response = "Okay, sounds good."

        if self.transcript_log:
            self.transcript_log[-1].setdefault("conversational_turns", []).append(
                {
                    "candidate_speech": transcript,
                    "ai_response": ai_response,
                }
            )

        await self.speak(ai_response)
        # Inactivity prompts apply only to greeting, main questions, and
        # follow-up questions—not to conversational clarification turns.
        self.current_interaction_state = "listening"

    async def _handle_skip(self, question_obj: dict, current_q: str, transcript: str):
        """Handles SKIP intent — saves 0-score evaluation and moves on."""
        if self.transcript_log:
            self.transcript_log[-1]["candidate_answer"] = transcript

        qa_entry = AnswerEvaluator.build_qa_entry(question_obj, current_q, transcript, self.current_question_idx + 1)
        await self.api_client.save_transcript(qa_entry)

        skip_eval = AnswerEvaluator.build_skip_evaluation(question_obj, transcript, self.current_question_idx + 1)
        if await self.api_client.save_evaluation(skip_eval):
            self.analysis_evaluations.append(skip_eval)

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

        is_follow_up_answer = primary_eval_data is not None
        if self.transcript_log and not is_follow_up_answer:
            # A real main answer replaces a preceding request to repeat it.
            self.transcript_log[-1]["candidate_answer"] = transcript

        filler = "Thank you for answering the question."
        
        # Start evaluation in the background so it runs concurrently with TTS
        import asyncio
        eval_task = asyncio.create_task(
            self.evaluator.evaluate_answer(
                current_question=current_q,
                transcript=transcript,
                expected_keywords=expected_keywords,
                answer_depth=answer_depth,
                follow_up_context=follow_up_context,
            )
        )

        # Speak the filler to avoid awkward silence
        await self.speak(filler)

        # Wait for the LLM evaluation to finish
        eval_data = await eval_task
        decision = eval_data.get("decision", "NEXT_QUESTION")
        is_complete = decision == "NEXT_QUESTION"
        follow_up_question = eval_data.get("suggested_follow_up", "")

        if decision == "REPEAT_QUESTION":
            # Do not consume a follow-up or persist REPEAT_QUESTION. If a
            # follow-up already exists, this repeats that same follow-up;
            # otherwise the next reply remains the main-question answer.
            if is_follow_up_answer and self.transcript_log:
                follow_ups = self.transcript_log[-1].get("follow_ups", [])
                repeat_text = (
                    follow_ups[-1].get("ai_response", current_q)
                    if follow_ups
                    else current_q
                )
            else:
                repeat_text = current_q
            if self.transcript_log:
                self.transcript_log[-1].setdefault("conversational_turns", []).append(
                    {
                        "candidate_speech": transcript,
                        "ai_response": f"Let me repeat the question: {repeat_text}",
                    }
                )
            await self.speak(f"Let me repeat the question: {repeat_text}")
            self._begin_listening()
            return

        if is_follow_up_answer and self.transcript_log:
            follow_ups = self.transcript_log[-1].get("follow_ups", [])
            if follow_ups:
                # The reply belongs to the already-asked follow-up, including
                # when that follow-up was clarified or repeated first.
                follow_ups[-1]["candidate_speech"] = transcript

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
                        "candidate_speech": "",
                        "ai_response": follow_up_question,
                    }
                )
            await self.speak(follow_up_question)
            self._begin_listening()
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
        if self.transcript_log and not self.transcript_log[-1].get("candidate_answer"):
            self.transcript_log[-1]["candidate_answer"] = transcript

        follow_ups = self.transcript_log[-1].get("follow_ups") if self.transcript_log else None
        primary_transcript = (
            self.transcript_log[-1].get("candidate_answer", transcript)
            if self.transcript_log
            else transcript
        )

        await persist_completed_question(
            self.api_client,
            self.analysis_evaluations,
            question_obj=question_obj,
            current_q=current_q,
            transcript=primary_transcript,
            primary_eval=primary_eval,
            current_eval=current_eval,
            question_number=self.current_question_idx + 1,
            follow_ups=follow_ups,
        )

        self.current_question_idx += 1
        await self._ask_next_question()

    # ──────────────────────────── QUESTION FLOW ────────────────────────────

    async def _ask_next_question(self):
        """Moves to the next question or closes the interview."""
        if not hasattr(self, "question_queues"):
            from src.screening_pipeline.routing_engine import initialize_queues
            self.question_queues = initialize_queues(self.questions)
            
        from src.screening_pipeline.routing_engine import get_next_question
        
        question_obj, termination_reason = get_next_question(self.question_queues, self.analysis_evaluations)
        
        if not question_obj:
            if termination_reason == "fatal_failure":
                from src.core.logger import logger
                logger.info("Candidate failed to recover. Terminating early.", extra={"session_id": self.session_id})
            await self._close_interview()
            return

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
        self._begin_listening()

    async def _close_interview(self):
        """Speak the closing and wait for its final conversational reply."""
        self.transcript_log.append(
            {
                "interaction_type": "closing",
                "bot_speech": CLOSING_TEXT,
                "candidate_answer": "",
            }
        )

        await self.speak(CLOSING_TEXT)
        # Closing is deliberately not a normal listening turn: it accepts one
        # candidate reply but never starts the 30-second "Are you there?" timer.
        self.current_interaction_state = "closing"
        self._closing_reply_timeout_task = asyncio.create_task(
            self._persist_closing_after_reply_timeout()
        )
        logger.info(
            "Started 30-second silent closing reply timeout",
            extra={"session_id": self.session_id},
        )

    async def _persist_closing_after_reply_timeout(self):
        """Persist and leave if the candidate does not reply to the closing."""
        try:
            await asyncio.sleep(CLOSING_REPLY_TIMEOUT_SECONDS)
        except asyncio.CancelledError:
            return

        if not self.is_active or self.current_interaction_state != "closing":
            return

        logger.info(
            "Closing reply timeout reached; saving interview and leaving",
            extra={"session_id": self.session_id},
        )
        await self._persist_closing_and_leave()

    async def _persist_closing_and_leave(self):
        """Persist the closing interaction, then request the bot leave."""
        self.current_interaction_state = "closing_persisting"
        self._cancel_closing_reply_timeout(reason="closing interaction completed")
        await self.finalize(reason="questions_completed")
        await self._leave_bot_after_close()
        self.is_active = False

    async def _leave_bot_after_close(self):
        """Ask Attendee to leave after the closing reply has been persisted."""
        metadata = getattr(self.session, "interview_metadata", None)
        bot_id = metadata.get("bot_id") if isinstance(metadata, dict) else None
        if not isinstance(bot_id, str) or not bot_id.strip():
            logger.warning(
                "Cannot leave meeting because the session has no bot_id",
                extra={"session_id": self.session_id},
            )
            return

        try:
            leave_result = await bot_client.leave_bot(bot_id)
        except Exception as err:
            logger.error(
                "Failed to request bot leave after interview close",
                extra={"session_id": self.session_id, "bot_id": bot_id, "error": str(err)},
            )
            return

        if leave_result.status == "leaving":
            logger.info(
                "Requested bot leave after interview close",
                extra={"session_id": self.session_id, "bot_id": bot_id},
            )
        else:
            logger.error(
                "Bot leave request was not accepted after interview close",
                extra={
                    "session_id": self.session_id,
                    "bot_id": bot_id,
                    "status": leave_result.status,
                    "error": leave_result.error_message,
                },
            )

    # ──────────────────────────── TTS ────────────────────────────

    async def speak(self, text: str):
        """Synthesizes text via TTS and streams audio to the WebSocket."""
        logger.info("AI speaking", extra={"text": text})
        self.current_interaction_state = "speaking"
        from src.screening_pipeline.audio_websocket import speak_to_attendee

        async for chunk in self.tts_client.synthesize(text):
            if not self.is_active:
                break
            await speak_to_attendee(self.websocket, chunk)
