"""Pipecat interview policy: screening state and business decisions."""

from __future__ import annotations

import asyncio

from typing import Any, Awaitable, Callable, Optional

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
    ANSWER_SETTLE_SECONDS,
    CLOSING_REPLY_TIMEOUT_SECONDS,
    CLOSING_TEXT,
    GREETING_TEXT,
    MAX_FOLLOW_UPS_PER_QUESTION,
    MAX_SILENCE_PROMPTS,
    SILENCE_PROMPT_SECONDS,
    SILENCE_PROMPT_TEXT,
)
from src.screening_pipeline.session_api import SessionApiClient
from src.screening_pipeline.speech_filter import is_probable_hallucination


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


class PipecatInterviewPolicy:
    """
    Manages the state machine for the AI interview.
    Coordinates Pipecat turn events, interview evaluation, and Core API persistence.
    """

    def __init__(
        self,
        session_id: str,
        *,
        evaluator: Optional[AnswerEvaluator] = None,
        llm_client: Optional[OllamaClient] = None,
        api_client: Optional[SessionApiClient] = None,
        speech_output: Optional[Callable[[str], Awaitable[None]]] = None,
    ):
        self.session_id = session_id
        self.session: Any = None
        self.questions: list = []
        self.current_question_idx = 0
        self.is_active = False

        resolved_llm = llm_client or OllamaClient()
        self.llm_client = resolved_llm
        self.evaluator = evaluator or AnswerEvaluator(resolved_llm)
        self.api_client = api_client  # Usually set after session load
        self.speech_output = speech_output

        self.current_interaction_state = "idle"  # idle, speaking, listening, evaluating
        self.transcript_log: list = []
        self.analysis_evaluations: list = []
        self.is_finalized = False
        self._inactivity_task: Optional[asyncio.Task] = None
        self._answer_settle_task: Optional[asyncio.Task] = None
        self._processing_task: Optional[asyncio.Task] = None
        self._closing_reply_timeout_task: Optional[asyncio.Task] = None
        self._last_candidate_activity_at: Optional[float] = None
        self._inactivity_cycle_started_at: Optional[float] = None
        self._silence_prompt_count = 0
        self._answer_buffer: list[str] = []
        self._end_lock = asyncio.Lock()
        self._ending = False
        self.termination_reason: Optional[str] = None


    # ──────────────────────────── LIFECYCLE ────────────────────────────

    async def start(self):
        """Initializes the interview session and speaks the greeting."""
        logger.info("Pipecat interview policy starting", extra={"session_id": self.session_id})

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
        self.is_active = True

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
                termination_reason=reason,
            )
        except Exception as err:
            logger.error(
                "Failed to finalize interview",
                extra={"session_id": self.session_id, "reason": reason, "error": str(err)},
            )

    async def end_interview(self, reason: str, *, leave_bot: bool = False) -> None:
        """End a session exactly once, regardless of which transport event won."""
        async with self._end_lock:
            if self._ending or self.is_finalized:
                return
            self._ending = True
            self.termination_reason = reason
            self.is_active = False
            self.current_interaction_state = "ending"
            self._cancel_inactivity_deadline()
            self._cancel_answer_settle()
            self._cancel_closing_reply_timeout()
            self._cancel_processing()
            await self.finalize(reason=reason)
            # The status endpoint has no termination-reason field yet; the
            # reason remains in this orchestration's durable finalization log.
            if self.api_client is not None:
                await self.api_client.update_status("completed")
            if leave_bot:
                await self._leave_bot_after_close()

    async def cleanup(self):
        """Teardown connections, persisting the interview first if it ended early."""
        await self.end_interview("transport_disconnected")

    # ──────────────────────────── PIPECAT TURN EVENTS ────────────────────────────

    def handle_candidate_speech(self, transcript: str):
        """Handle one finalized Pipecat transcription."""
        if self.current_interaction_state == "closing":
            self._cancel_closing_reply_timeout(reason="closing reply transcript received")
        if not self.is_active or self.current_interaction_state not in {
            "listening", "collecting_answer", "evaluating", "speaking", "closing"
        }:
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

        logger.info("Candidate speech received", extra={"transcript": transcript})
        if self.transcript_log:
            silence_prompts = self.transcript_log[-1].get("silence_prompts", [])
            if silence_prompts and not silence_prompts[-1].get("candidate_reply"):
                silence_prompts[-1]["candidate_reply"] = transcript
        if self.current_interaction_state == "closing":
            self._processing_task = asyncio.create_task(self._process_speech(transcript))
            return

        self._answer_buffer.append(transcript.strip())
        self.current_interaction_state = "collecting_answer"
        self._cancel_answer_settle()
        self._answer_settle_task = asyncio.create_task(self._process_after_answer_settles())

    def handle_candidate_activity(self):
        """Extend the deadline and invalidate stale work as soon as VAD fires."""
        if not self.is_active:
            return
        now = asyncio.get_running_loop().time()
        self._last_candidate_activity_at = now
        self._inactivity_cycle_started_at = now
        if self.current_interaction_state == "closing":
            self._cancel_closing_reply_timeout(reason="closing reply detected by VAD")
            return
        if self.current_interaction_state == "evaluating":
            self._cancel_processing()
            self.current_interaction_state = "collecting_answer"
        self._cancel_answer_settle()

    def _begin_listening(self):
        """Enter an eligible listening turn and start its hard inactivity deadline."""
        self.current_interaction_state = "listening"
        self._answer_buffer.clear()
        self._start_inactivity_deadline()
        logger.info(
            "Started 30-second candidate inactivity timer",
            extra={"session_id": self.session_id},
        )

    def _start_inactivity_deadline(self):
        self._cancel_inactivity_deadline()
        now = asyncio.get_running_loop().time()
        self._last_candidate_activity_at = now
        self._inactivity_cycle_started_at = now
        self._silence_prompt_count = 0
        self._inactivity_task = asyncio.create_task(self._end_after_inactivity())

    def _cancel_inactivity_deadline(self):
        task = self._inactivity_task
        if task and not task.done() and task is not asyncio.current_task():
            task.cancel()
        self._inactivity_task = None

    def _cancel_answer_settle(self):
        task = self._answer_settle_task
        if task and not task.done() and task is not asyncio.current_task():
            task.cancel()
        self._answer_settle_task = None

    def _cancel_processing(self):
        task = self._processing_task
        if task and not task.done() and task is not asyncio.current_task():
            task.cancel()
        self._processing_task = None

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

    async def _end_after_inactivity(self):
        """Prompt twice, then end after a third unanswered 30-second window."""
        try:
            while self.is_active:
                cycle_started_at = self._inactivity_cycle_started_at
                if cycle_started_at is None:
                    return
                remaining = SILENCE_PROMPT_SECONDS - (
                    asyncio.get_running_loop().time() - cycle_started_at
                )
                if remaining > 0:
                    await asyncio.sleep(remaining)
                    continue
                if self.current_interaction_state in {"listening", "collecting_answer"}:
                    if self._silence_prompt_count < MAX_SILENCE_PROMPTS:
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
                                {"bot_speech": SILENCE_PROMPT_TEXT, "candidate_reply": ""}
                            )
                        # A bot prompt starts a new 30-second response window;
                        # only candidate VAD activity can reset it early.
                        self._inactivity_cycle_started_at = asyncio.get_running_loop().time()
                        await self.speak(SILENCE_PROMPT_TEXT)
                        if self.is_active and self.current_interaction_state == "speaking":
                            self.current_interaction_state = "listening"
                        continue

                    logger.info("Candidate inactivity deadline reached", extra={"session_id": self.session_id})
                    await self.speak(CLOSING_TEXT)
                    await self.end_interview("candidate_silence", leave_bot=True)
                return
        except asyncio.CancelledError:
            return

    async def _process_after_answer_settles(self):
        try:
            await asyncio.sleep(ANSWER_SETTLE_SECONDS)
            if not self.is_active or self.current_interaction_state != "collecting_answer":
                return
            transcript = " ".join(part for part in self._answer_buffer if part).strip()
            if not transcript:
                return
            self.current_interaction_state = "evaluating"
            self._cancel_inactivity_deadline()
            self._processing_task = asyncio.create_task(self._process_speech(transcript))
            await self._processing_task
        except asyncio.CancelledError:
            return

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

        question_obj = getattr(self, "current_question_obj", {})
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
        # A request for time is still a response turn. Never leave a session
        # indefinitely waiting after conversational speech.
        self._begin_listening()

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

        # Evaluate the answer synchronously to determine the next step
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
        if decision != "REPEAT_QUESTION":
            await self.speak("Thank you for answering the question.")

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
            interaction = self.transcript_log[-1] if self.transcript_log else None
            repeat_count = interaction.get("question_repeat_count", 0) if interaction else 0
            if repeat_count < 1:
                ai_response = f"Let me repeat the question: {repeat_text}"
                if interaction:
                    interaction["question_repeat_count"] = repeat_count + 1
            else:
                ai_response = (
                    "I have already repeated the question once. "
                    "Please share your best answer when you are ready."
                )
            if interaction:
                interaction.setdefault("conversational_turns", []).append(
                    {"candidate_speech": transcript, "ai_response": ai_response}
                )
            await self.speak(ai_response)
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
                self.termination_reason = "fatal_failure"
            await self._close_interview()
            return

        self.current_question_obj = question_obj
        q_text = question_obj.get("question", "")

        self.transcript_log.append(
            {
                "interaction_type": "question",
                "question_id": question_obj.get("id"),
                "bot_speech": q_text,
                "candidate_answer": "",
                "follow_ups": [],
                "question_repeat_count": 0,
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
        reason = getattr(self, "termination_reason", "questions_completed")
        await self.end_interview(reason or "questions_completed", leave_bot=True)

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

    # ──────────────────────────── PIPECAT TTS OUTPUT ────────────────────────────

    async def speak(self, text: str):
        """Queue policy-generated speech in the Pipecat TTS pipeline."""
        logger.info("AI speaking", extra={"text": text})
        self.current_interaction_state = "speaking"
        if self.speech_output is None:
            raise RuntimeError("Pipecat speech output is not configured")
        await self.speech_output(text)
