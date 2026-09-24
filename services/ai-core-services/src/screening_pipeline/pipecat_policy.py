"""Pipecat interview policy: screening state and business decisions."""

from __future__ import annotations

import asyncio
import random

from typing import Any, Awaitable, Callable, Optional

from src.core.logger import logger
from src.llm.client import OllamaClient
from src.meeting_bot.client import bot_client
from src.meeting_bot.repository import interview_session_repo
from src.screening_pipeline.evaluator import AnswerEvaluator
from src.screening_pipeline.persistence import (
    build_completed_question_payload,
    persist_interview_close,
    persist_qa_and_evaluation,
)
from src.screening_pipeline.prompts import (
    ANSWER_ACKNOWLEDGEMENT_TEXT,
    ANSWER_SETTLE_SECONDS,
    CANDIDATE_SPEAKING_POLL_SECONDS,
    CLOSING_REPLY_TIMEOUT_SECONDS,
    CLOSING_TEXT,
    FILLER_SCHEDULE_SECONDS,
    FILLER_TEXTS,
    GREETING_TEXT,
    MAX_FOLLOW_UPS_PER_QUESTION,
    MAX_SILENCE_PROMPTS,
    REPEAT_QUESTION_LIMIT_TEXT,
    REPEAT_QUESTION_PREFIX_TEXT,
    SILENCE_PROMPT_SECONDS,
    SILENCE_PROMPT_TEXT,
)
from src.screening_pipeline.session_api import SessionApiClient
from src.screening_pipeline.speech_filter import is_probable_hallucination
from src.screening_pipeline.tts_prewarm import coerce_questions_list, known_bot_texts


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
        tts_cache_warmer: Optional[Callable[[list[str]], Awaitable[None]]] = None,
    ):
        self.session_id = session_id
        self.session: Any = None
        self.questions: list = []
        self.current_question_idx = 0
        self.is_active = False
        self.tts_cache_warmer = tts_cache_warmer
        self._tts_warm_task: Optional[asyncio.Task] = None

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
        self._pending_persist_tasks: list[asyncio.Task] = []
        # True from VAD "started speaking" until VAD confirms "stopped
        # speaking" — used to hold off the "Are you there?" inactivity
        # prompt during one long, unbroken candidate answer (see
        # _end_after_inactivity / handle_candidate_speech_stopped).
        self._candidate_speaking = False
        self._last_filler_text: Optional[str] = None
        # Set by handle_candidate_speech_stopped (or, as a fallback,
        # _process_after_answer_settles) to the moment the candidate's speech
        # was received; read (and cleared) by _start_filler_schedule to
        # back-date the filler schedule. None outside a turn in progress.
        self._turn_started_at: Optional[float] = None
        # Runs for the settle-wait + classify_and_evaluate span of a turn;
        # see _start_filler_schedule / _cancel_filler_schedule / _run_filler_schedule.
        self._filler_task: Optional[asyncio.Task] = None


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

        self.questions = coerce_questions_list(self.session.generated_questions)
        self.is_active = True

        # Fire-and-forget: warms the TTS cache for known bot text (greeting,
        # questions, closing, silence prompt, acknowledgement) in the
        # background so later speak() calls for that text skip synthesis.
        # Does not block the greeting itself. See
        # docs/architecture/SCREENING_BOT_LATENCY_OPTIMIZATION.md Phase 4.
        if self.tts_cache_warmer is not None:
            self._tts_warm_task = asyncio.create_task(self._warm_tts_cache())

        self.transcript_log.append(
            {
                "interaction_type": "greeting",
                "bot_speech": GREETING_TEXT,
                "candidate_answer": "",
            }
        )
        await self.speak(GREETING_TEXT)
        self._begin_listening()

    async def _warm_tts_cache(self) -> None:
        """Pre-synthesize all deterministic bot text for this session.

        Runs in the background starting right after questions are loaded, so
        by the time each question is actually asked its audio is already
        cached (see KokoroSynthesizer.warm). Never raises: a warm-up failure
        must fall back to normal on-demand synthesis, not break the session.
        """
        texts = known_bot_texts(self.questions)
        try:
            await self.tts_cache_warmer(texts)
        except asyncio.CancelledError:
            raise
        except Exception as err:
            logger.error(
                "Failed to warm TTS cache",
                extra={"session_id": self.session_id, "error": str(err)},
            )

    def _cancel_tts_warm(self):
        task = self._tts_warm_task
        if task and not task.done() and task is not asyncio.current_task():
            task.cancel()
        self._tts_warm_task = None

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
        # Per-question Core API saves run in the background (see
        # _schedule_persist); give in-flight ones a bounded chance to land
        # before teardown instead of abandoning them mid-flight.
        await self._flush_pending_persist()
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
            self._cancel_filler_schedule()
            self._cancel_tts_warm()
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

    # ──────────────────────────── BACKGROUND PERSISTENCE ────────────────────────────

    def _schedule_persist(self, coro: Awaitable[None]) -> None:
        """Run a per-question Core API save in the background.

        Keeps `_ask_next_question` (and the next bot utterance) off the Core
        API round-trip. Tracked in `_pending_persist_tasks` so finalize() can
        wait for stragglers instead of dropping them on teardown.
        """
        task = asyncio.create_task(self._run_persist(coro))
        self._pending_persist_tasks.append(task)
        task.add_done_callback(
            lambda t: self._pending_persist_tasks.remove(t)
            if t in self._pending_persist_tasks
            else None
        )

    async def _run_persist(self, coro: Awaitable[None]) -> None:
        try:
            await coro
        except Exception as err:
            logger.error(
                "Background Core API persistence failed",
                extra={"session_id": self.session_id, "error": str(err)},
            )

    async def _flush_pending_persist(self, timeout: float = 10.0) -> None:
        """Wait for in-flight background Core API saves before teardown."""
        tasks = [t for t in self._pending_persist_tasks if not t.done()]
        if not tasks:
            return
        try:
            await asyncio.wait_for(asyncio.gather(*tasks), timeout=timeout)
        except asyncio.TimeoutError:
            logger.error(
                "Timed out waiting for background Core API persistence to finish",
                extra={"session_id": self.session_id, "pending": len(tasks)},
            )

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
        self._candidate_speaking = True
        if self.current_interaction_state == "closing":
            self._cancel_closing_reply_timeout(reason="closing reply detected by VAD")
            return
        if self.current_interaction_state == "evaluating":
            self._cancel_processing()
            self.current_interaction_state = "collecting_answer"
        self._cancel_answer_settle()

    def handle_candidate_speech_stopped(self):
        """VAD confirmed the candidate actually stopped talking.

        Ends the grace window _end_after_inactivity holds open while
        _candidate_speaking is True (see there), and gives the candidate a
        fresh SILENCE_PROMPT_SECONDS window starting now — mirroring the
        reset handle_candidate_activity does on speech start, so a candidate
        who just finished a long answer isn't immediately treated as having
        gone silent 30 seconds ago.
        """
        if not self.is_active:
            return
        self._candidate_speaking = False
        now = asyncio.get_running_loop().time()
        self._last_candidate_activity_at = now
        self._inactivity_cycle_started_at = now
        # Earliest available proxy for "the candidate stopped talking" — well
        # before STT finalizes a transcript and handle_candidate_speech even
        # runs. _start_filler_schedule measures FILLER_SCHEDULE_SECONDS from
        # here, so STT latency counts against that schedule instead of the
        # first filler landing STT + FILLER_SCHEDULE_SECONDS[0] after the
        # candidate actually stopped. Overwritten by every VAD stop, so only
        # the final one before real processing starts is ever used.
        self._turn_started_at = now

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
                if self._candidate_speaking:
                    # VAD hasn't confirmed the candidate stopped talking yet
                    # (a single answer running past SILENCE_PROMPT_SECONDS) —
                    # do not interrupt them with "Are you there?". Poll again
                    # shortly; handle_candidate_speech_stopped resets the
                    # deadline once VAD confirms they actually finished.
                    await asyncio.sleep(CANDIDATE_SPEAKING_POLL_SECONDS)
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
        # Normally already set by handle_candidate_speech_stopped (VAD
        # confirming the candidate stopped talking, before STT even finalizes
        # a transcript) — this is only a fallback for callers that push a
        # transcript without a preceding VAD-stop event (e.g. direct
        # handle_candidate_speech calls in tests). _start_filler_schedule
        # reads it so FILLER_SCHEDULE_SECONDS is measured from here, already
        # accounting for STT latency and (per _run_filler_schedule) able to
        # fire during the settle wait itself, not just after it.
        if self._turn_started_at is None:
            self._turn_started_at = asyncio.get_running_loop().time()
        # Started now, before the settle sleep below, so a filler can land
        # during settle if the schedule calls for it — safe because a
        # candidate resuming speech mid-settle already triggers the same
        # InterruptionFrame barge-in handling any other bot utterance gets
        # (see handle_candidate_activity), regardless of current_interaction_state.
        # Cancelled in the finally below for every path that doesn't reach
        # classify_and_evaluate (see _process_speech), and again there right
        # after that call resolves — a filler must never overlap real speech.
        self._start_filler_schedule()
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
        finally:
            self._cancel_filler_schedule()

    # ──────────────────────────── MAIN PROCESSING ────────────────────────────

    async def _process_speech(self, transcript: str):
        """Routes the candidate's speech through a single intent + evaluation LLM call."""
        if self.transcript_log and self.transcript_log[-1].get("interaction_type") == "closing":
            # Never reaches classify_and_evaluate, so no filler is ever
            # needed here — cancel now rather than leaving it ticking
            # through _persist_closing_and_leave.
            self._cancel_filler_schedule()
            # The closing reply is conversational only. Persist it in the full
            # transcript before instructing the meeting bot to leave.
            self.transcript_log[-1]["candidate_answer"] = transcript
            await self._persist_closing_and_leave()
            return

        if self.transcript_log and self.transcript_log[-1].get("interaction_type") == "greeting":
            # Same reasoning: _ask_next_question speaks the first real
            # question directly, with no classify_and_evaluate call to wait
            # on, so a filler must not still be armed when it does.
            self._cancel_filler_schedule()
            self.transcript_log[-1]["candidate_answer"] = transcript
            await self._ask_next_question()
            return

        question_obj = getattr(self, "current_question_obj", {})
        current_q = question_obj.get("question", "")

        # Evaluation context is needed up front because the single LLM call below
        # decides intent and (if ANSWERING) scores the answer together.
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

        try:
            result = await self.evaluator.classify_and_evaluate(
                current_question=current_q,
                transcript=transcript,
                expected_keywords=expected_keywords,
                answer_depth=answer_depth,
                follow_up_context=follow_up_context,
            )
        finally:
            # We now know what to say — a filler must never speak over (or
            # right before, mid-utterance) the real response that follows.
            self._cancel_filler_schedule()
        intent = result.get("intent", "ANSWERING")

        if intent in ["CLARIFICATION", "SMALL_TALK"]:
            await self._handle_conversational(transcript, result.get("response", ""))
            return

        if intent == "SKIP":
            await self._handle_skip(question_obj, current_q, transcript)
            return

        await self._handle_answer(question_obj, current_q, transcript, result, primary_eval_data)

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
        """Handles SKIP intent — saves 0-score evaluation and moves on.

        analysis_evaluations is updated synchronously (routing reads it right
        after this returns); the Core API save runs in the background.
        """
        if self.transcript_log:
            self.transcript_log[-1]["candidate_answer"] = transcript

        qa_entry = AnswerEvaluator.build_qa_entry(question_obj, current_q, transcript, self.current_question_idx + 1)
        skip_eval = AnswerEvaluator.build_skip_evaluation(question_obj, transcript, self.current_question_idx + 1)
        self.analysis_evaluations.append(skip_eval)
        self._schedule_persist(persist_qa_and_evaluation(self.api_client, qa_entry, skip_eval))

        self.current_question_idx += 1
        await self._ask_next_question()

    async def _handle_answer(
        self,
        question_obj: dict,
        current_q: str,
        transcript: str,
        eval_data: dict,
        primary_eval_data: Optional[dict] = None,
    ):
        """Handles ANSWERING intent using the evaluation already produced by the
        single classify_and_evaluate call — decides follow-up or next question."""
        is_follow_up_answer = primary_eval_data is not None
        if self.transcript_log and not is_follow_up_answer:
            # A real main answer replaces a preceding request to repeat it.
            self.transcript_log[-1]["candidate_answer"] = transcript

        decision = eval_data.get("decision", "NEXT_QUESTION")
        is_complete = decision == "NEXT_QUESTION"
        follow_up_question = eval_data.get("suggested_follow_up", "")
        if decision != "REPEAT_QUESTION":
            await self.speak(ANSWER_ACKNOWLEDGEMENT_TEXT)

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
                if interaction:
                    interaction["question_repeat_count"] = repeat_count + 1
                    interaction.setdefault("conversational_turns", []).append(
                        {
                            "candidate_speech": transcript,
                            "ai_response": f"{REPEAT_QUESTION_PREFIX_TEXT} {repeat_text}",
                        }
                    )
                # Two separate speak() calls, not one concatenated string:
                # repeat_text is spoken verbatim so it hits the TTS cache
                # (pre-warmed as-is) instead of missing on a prefixed variant
                # that was never cached (see prompts.REPEAT_QUESTION_PREFIX_TEXT).
                await self.speak(REPEAT_QUESTION_PREFIX_TEXT)
                await self.speak(repeat_text)
            else:
                if interaction:
                    interaction.setdefault("conversational_turns", []).append(
                        {
                            "candidate_speech": transcript,
                            "ai_response": REPEAT_QUESTION_LIMIT_TEXT,
                        }
                    )
                await self.speak(REPEAT_QUESTION_LIMIT_TEXT)
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
        """Records the completed question and saves it to core-api in the background.

        analysis_evaluations is updated synchronously — routing
        (get_next_question, called from _ask_next_question right below) reads
        it immediately and must see this question's result. Only the Core API
        HTTP save is deferred to the background.
        """
        if self.transcript_log and not self.transcript_log[-1].get("candidate_answer"):
            self.transcript_log[-1]["candidate_answer"] = transcript

        follow_ups = self.transcript_log[-1].get("follow_ups") if self.transcript_log else None
        primary_transcript = (
            self.transcript_log[-1].get("candidate_answer", transcript)
            if self.transcript_log
            else transcript
        )

        qa_entry, evaluation = build_completed_question_payload(
            question_obj=question_obj,
            current_q=current_q,
            transcript=primary_transcript,
            primary_eval=primary_eval,
            current_eval=current_eval,
            question_number=self.current_question_idx + 1,
            follow_ups=follow_ups,
        )
        self.analysis_evaluations.append(evaluation)
        self._schedule_persist(persist_qa_and_evaluation(self.api_client, qa_entry, evaluation))

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

    async def _speak_filler(self, text: str) -> None:
        """Speak a short filler phrase without changing current_interaction_state.

        Unlike speak(), this deliberately leaves current_interaction_state
        untouched: fillers can play during "collecting_answer" (settle) or
        "evaluating" (see _run_filler_schedule), and handle_candidate_activity
        relies on that state to cancel the in-flight LLM call on barge-in
        during "evaluating". If a filler flipped the state to "speaking", a
        candidate interrupting while a filler plays would be missed.
        """
        logger.info("AI speaking filler", extra={"text": text})
        if self.speech_output is None:
            raise RuntimeError("Pipecat speech output is not configured")
        await self.speech_output(text)

    def _start_filler_schedule(self) -> None:
        """Arm the filler schedule for this turn. See _run_filler_schedule."""
        self._cancel_filler_schedule()
        self._filler_task = asyncio.create_task(self._run_filler_schedule())

    def _cancel_filler_schedule(self) -> None:
        """Disarm the filler schedule — a real response is either already
        being spoken, or about to be. Safe to call even when nothing is
        running (e.g. every turn that never needed a filler at all)."""
        task = self._filler_task
        if task and not task.done() and task is not asyncio.current_task():
            task.cancel()
        self._filler_task = None

    async def _run_filler_schedule(self) -> None:
        """Speak a short random filler ("Alright, one moment.", ...) at each
        offset in FILLER_SCHEDULE_SECONDS, measured from when the candidate
        stopped talking — not from whatever moment this task happened to
        start — so it doesn't drift later just because a filler itself took a
        moment to speak. Runs independently of settle/classify_and_evaluate;
        the caller cancels it (see _cancel_filler_schedule) the instant a real
        response is known, whether that's immediately (closing/greeting
        replies never need a filler at all) or after the LLM call resolves.
        Deliberately allowed to fire *during* the settle wait, not only after
        it: a candidate resuming speech mid-settle already triggers the same
        InterruptionFrame barge-in handling as any other bot utterance (see
        handle_candidate_activity), so there's no dead-air-vs-safety tradeoff
        in starting the clock this early.
        """
        loop = asyncio.get_running_loop()
        started_at = self._turn_started_at
        self._turn_started_at = None
        reference_time = started_at if started_at is not None else loop.time()
        for offset in FILLER_SCHEDULE_SECONDS:
            timeout = max(0.0, (reference_time + offset) - loop.time())
            await asyncio.sleep(timeout)
            await self._speak_filler(self._pick_random_filler())

    def _pick_random_filler(self) -> str:
        """Random filler text, never repeating the one spoken immediately before."""
        candidates = FILLER_TEXTS
        if len(FILLER_TEXTS) > 1 and self._last_filler_text is not None:
            candidates = [text for text in FILLER_TEXTS if text != self._last_filler_text]
        choice = random.choice(candidates)
        self._last_filler_text = choice
        return choice
