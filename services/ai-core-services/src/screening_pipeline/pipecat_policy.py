"""Pipecat interview policy: screening state and business decisions."""

from __future__ import annotations

import asyncio
import random

from typing import Any, Awaitable, Callable, Optional

from src.core.logger import logger
from src.llm.client import OllamaClient
from src.meeting_bot.attendee import attendee_client
from src.meeting_bot.client import bot_client
from src.meeting_bot.repository import interview_session_repo
from src.screening_pipeline.evaluator import AnswerEvaluator
from src.screening_pipeline.persistence import (
    build_completed_question_payload,
    persist_interview_close,
    persist_qa_and_evaluation,
)
from src.screening_pipeline.candidate_presence import (
    apply_participant_event,
    candidate_camera_on,
    forget_session,
    is_candidate_present,
    speech_may_start_interview,
)
from src.screening_pipeline.finished_interviews import interview_finished, mark_interview_finished
from src.screening_pipeline.prompts import (
    ANSWER_ACKNOWLEDGEMENT_TEXT,
    CANDIDATE_JOIN_POLL_SECONDS,
    CANDIDATE_JOIN_WAIT_SECONDS,
    ANSWER_SETTLE_SECONDS,
    CANDIDATE_SPEAKING_POLL_SECONDS,
    CLOSING_REPLY_TIMEOUT_SECONDS,
    CLOSING_TEXT,
    FILLER_SCHEDULE_SECONDS,
    FILLER_TEXTS,
    GREETING_REPLY_TIMEOUT_SECONDS,
    GREETING_TEXT,
    MAX_CONVERSATIONAL_TURNS_PER_QUESTION,
    MAX_FOLLOW_UPS_PER_QUESTION,
    MAX_NON_ANSWER_REASKS_PER_QUESTION,
    MAX_SILENCE_PROMPTS,
    MOVE_ON_TEXT,
    REPEAT_QUESTION_LIMIT_TEXT,
    REPEAT_QUESTION_PREFIX_TEXT,
    RESUME_TEXT,
    SILENCE_PROMPT_SECONDS,
    SILENCE_PROMPT_TEXT,
    START_WITHOUT_REPLY_TEXT,
    candidate_did_not_join_note,
    camera_not_on_note,
    CAMERA_PROMPT_INTERVAL_SECONDS,
    CAMERA_PROMPT_TEXT,
    DEFAULT_INTERVIEW_MINUTES,
    FINAL_QUESTION_CATEGORIES,
    NO_NEW_QUESTION_IN_LAST_SECONDS,
    build_greeting,
    STT_RESULT_GRACE_SECONDS,
    UNFINISHED_ANSWER_EXTRA_SECONDS,
)
from src.screening_pipeline.routing_engine import initialize_queues
from src.screening_pipeline.session_api import SessionApiClient, normalize_interview_metadata
from src.screening_pipeline.speech_filter import (
    is_probable_hallucination,
    is_skip_request,
    looks_unfinished,
)
from src.screening_pipeline.tts_prewarm import coerce_questions_list, known_bot_texts


# A session in one of these states has ended; never run its interview again.
_FINISHED_SESSION_STATUSES = frozenset({"completed", "failed", "cancelled", "no_show"})


def _answered_follow_ups(follow_ups: Any) -> list:
    """Follow-ups the candidate replied to, for the Q&A save: core-api rejects
    (422) one with an empty answer, losing the whole question. The transcript
    keeps the unanswered ones so HR sees the follow-up was asked."""
    if not isinstance(follow_ups, list):
        return []
    return [
        f
        for f in follow_ups
        if isinstance(f, dict) and str(f.get("candidate_speech") or "").strip()
    ]


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
        # Opening line with the company / role details HR wrote (set on start).
        self.greeting_text: str = GREETING_TEXT
        self.current_question_idx = 0
        self.is_active = False
        self.tts_cache_warmer = tts_cache_warmer
        # Fully synthesizes a line before it is spoken (set by the runtime).
        self.speech_preparer: Optional[Callable[[str], Awaitable[None]]] = None
        self._tts_warm_task: Optional[asyncio.Task] = None

        resolved_llm = llm_client or OllamaClient()
        self.llm_client = resolved_llm
        self.evaluator = evaluator or AnswerEvaluator(resolved_llm)
        self.api_client = api_client  # Usually set after session load
        self.speech_output = speech_output

        self.current_interaction_state = "idle"  # idle, speaking, listening, evaluating
        self.transcript_log: list = []
        self.analysis_evaluations: list = []
        # (question_obj, question text) while its follow-up awaits a reply; the
        # main answer's evaluation sits on that question's transcript entry.
        self._question_awaiting_follow_up: Optional[tuple[dict, str]] = None
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
        # Shown to HR with the final status (e.g. why it's a no-show).
        self._status_note: Optional[str] = None
        self._candidate_name: Optional[tuple] = None
        # The candidate is in the meeting (the camera may still be off), and
        # the "please turn on your camera" reminder loop.
        self._candidate_seen = False
        self._camera_prompt_task: Optional[asyncio.Task] = None
        # "Let's move on…" waiting to be said before the next question.
        self._pending_transition_text: Optional[str] = None
        # When the candidate first heard the bot (greeting / resume): the
        # booked interview time is counted from here.
        self._interview_started_at: Optional[float] = None
        # The one extra Good-to-have / Skill-gap question allowed in the last
        # minutes of the booked time has been asked (no follow-up on it).
        self._final_question_asked = False
        self._pending_persist_tasks: list[asyncio.Task] = []
        self._question_save_lock = asyncio.Lock()
        # True from VAD "started speaking" until VAD confirms "stopped
        # speaking" — used to hold off the "Are you there?" inactivity
        # prompt during one long, unbroken candidate answer (see
        # _end_after_inactivity / handle_candidate_speech_stopped).
        self._candidate_speaking = False
        self._last_filler_text: Optional[str] = None
        # Whether a filler already played for the current answer; suppresses
        # the acknowledgement right after it (Bug-041).
        self._filler_spoken_this_turn = False
        # Set by handle_candidate_speech_stopped (or, as a fallback,
        # _process_after_answer_settles) to the moment the candidate's speech
        # was received; read (and cleared) by _start_filler_schedule to
        # back-date the filler schedule. None outside a turn in progress.
        self._turn_started_at: Optional[float] = None
        # Runs for the settle-wait + classify_and_evaluate span of a turn;
        # see _start_filler_schedule / _cancel_filler_schedule / _run_filler_schedule.
        self._filler_task: Optional[asyncio.Task] = None
        # Runs while the bot waits in the meeting for the candidate to join.
        self._candidate_wait_task: Optional[asyncio.Task] = None


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

        if getattr(self.session, "status", None) in _FINISHED_SESSION_STATUSES:
            # Attendee reconnects the audio stream while the bot is leaving.
            # Starting again greeted a meeting that was ending, and on
            # disconnect saved a greeting-only transcript over the real one.
            logger.info(
                "Session already finished; not starting the interview again",
                extra={"session_id": self.session_id, "status": self.session.status},
            )
            return

        if interview_finished(self._session_bot_id()):
            # Same reconnect, but the ending runtime hasn't written its
            # status yet. Staying idle keeps api_client unset, so this runtime
            # never saves a summary or status (Bugs 44-46).
            logger.info(
                "Interview for this bot already ended in this process; not starting again",
                extra={"session_id": self.session_id},
            )
            return

        if self.api_client is None:
            self.api_client = SessionApiClient(session_id=str(self.session.id))

        self.questions = coerce_questions_list(self.session.generated_questions)
        self.greeting_text = await self._personal_greeting()
        self.is_active = True

        # Fire-and-forget: warms the TTS cache for known bot text (greeting,
        # questions, closing, silence prompt, acknowledgement) in the
        # background so later speak() calls for that text skip synthesis.
        # Does not block the greeting itself. See
        # docs/architecture/SCREENING_BOT_LATENCY_OPTIMIZATION.md Phase 4.
        if self.tts_cache_warmer is not None:
            self._tts_warm_task = asyncio.create_task(self._warm_tts_cache())

        if await self._resume_saved_progress():
            return

        if is_candidate_present(self.session_id) and candidate_camera_on(self.session_id):
            await self._greet()
            return
        # Don't talk to an empty meeting: greet when the candidate joins
        # (with the camera on).
        self.current_interaction_state = "waiting_for_candidate"
        self._candidate_wait_task = asyncio.create_task(self._wait_for_candidate())
        logger.info(
            "Waiting for the candidate to join",
            extra={
                "session_id": self.session_id,
                "wait_seconds": CANDIDATE_JOIN_WAIT_SECONDS,
                "poll_seconds": CANDIDATE_JOIN_POLL_SECONDS,
            },
        )
        if is_candidate_present(self.session_id):
            await self.candidate_joined()  # here, camera off: ask for it

    async def _resume_saved_progress(self) -> bool:
        """Continue an interview a previous runtime left mid-way.

        The service restarted during an interview: Attendee reconnected the
        bot, which still sat in the meeting, and the new runtime greeted and
        asked question 1 again. The re-asked questions ("I already answered
        this") were saved as skips over the real scores, and the final
        summary and transcript held only what came after the restart.

        Progress is read from what was saved after each question: the
        conversation transcript (written per question; a reschedule rebuilds
        the metadata, so it always belongs to this attempt) and the
        evaluations of the questions in it. Returns False when there is
        nothing to resume.
        """
        metadata = getattr(self.session, "interview_metadata", None)
        saved_transcript = (
            metadata.get("conversation_transcript") if isinstance(metadata, dict) else None
        )
        if not isinstance(saved_transcript, list):
            return False
        asked_ids = {
            entry.get("question_id")
            for entry in saved_transcript
            if isinstance(entry, dict)
            and entry.get("interaction_type") == "question"
            and entry.get("question_id") is not None
        }
        if not asked_ids:
            return False
        evaluations = [
            evaluation
            for evaluation in await interview_session_repo.get_saved_evaluations(self.session_id)
            if evaluation.get("question_id") in asked_ids
        ]
        if not evaluations:
            return False

        answered_ids = {evaluation.get("question_id") for evaluation in evaluations}
        self.analysis_evaluations = evaluations
        self.current_question_idx = len(evaluations)
        # Routing is deterministic in (queues, evaluations): with the answered
        # questions removed it picks the question that was interrupted.
        self.question_queues = {
            category: [q for q in queue if q.get("id") not in answered_ids]
            for category, queue in initialize_queues(self.questions).items()
        }
        self.transcript_log = [dict(entry) for entry in saved_transcript if isinstance(entry, dict)]
        self.transcript_log.append(
            {"interaction_type": "resume", "bot_speech": RESUME_TEXT, "candidate_answer": ""}
        )
        logger.info(
            "Resuming an interview that was already underway",
            extra={"session_id": self.session_id, "answered_questions": len(evaluations)},
        )
        self._mark_interview_started()
        await self.speak(RESUME_TEXT)
        await self._ask_next_question()
        return True

    def _mark_interview_started(self) -> None:
        if self._interview_started_at is None:
            self._interview_started_at = asyncio.get_running_loop().time()

    def _interview_minutes(self) -> float:
        metadata = getattr(self.session, "interview_metadata", None)
        minutes = metadata.get("duration_minutes") if isinstance(metadata, dict) else None
        if isinstance(minutes, (int, float)) and not isinstance(minutes, bool) and minutes > 0:
            return float(minutes)
        return float(DEFAULT_INTERVIEW_MINUTES)

    def _seconds_left(self) -> Optional[float]:
        """Seconds until the end of the booked time (negative once past it)."""
        if self._interview_started_at is None:
            return None
        elapsed = asyncio.get_running_loop().time() - self._interview_started_at
        return self._interview_minutes() * 60 - elapsed

    def _out_of_time(self) -> bool:
        """True in the last NO_NEW_QUESTION_IN_LAST_SECONDS of the booked time."""
        left = self._seconds_left()
        return left is not None and left <= NO_NEW_QUESTION_IN_LAST_SECONDS

    def _final_question(self) -> Optional[dict]:
        """In the last minutes, one more question is allowed if a Good-to-have
        (else Skill-gap) question is still unasked: running 1-2 minutes over
        is fine. Only while there is booked time left, and only once."""
        left = self._seconds_left()
        if self._final_question_asked or left is None or left <= 0:
            return None
        for category in FINAL_QUESTION_CATEGORIES:
            queue = getattr(self, "question_queues", {}).get(category)
            if queue:
                self._final_question_asked = True
                return queue.pop(0)
        return None

    async def _personal_greeting(self) -> str:
        """Opening with the company and role details HR wrote; the standard
        greeting when there are none or they can't be read."""
        application_id = getattr(self.session, "application_id", None)
        if not isinstance(application_id, str) or not application_id:
            return GREETING_TEXT
        intro = await interview_session_repo.get_interview_intro(application_id)
        return build_greeting(**intro) if intro else GREETING_TEXT

    async def _greet(self) -> None:
        greeting = getattr(self, "greeting_text", None) or GREETING_TEXT
        # The company / role greeting is long; if its audio isn't cached yet,
        # finish it before speaking so it plays in one go, not sentence by
        # sentence with silences while the next one is synthesized.
        if self.speech_preparer is not None:
            try:
                await self.speech_preparer(greeting)
            except asyncio.CancelledError:
                raise
            except Exception as err:
                logger.warning(
                    "Could not prepare the greeting audio; speaking it as it is made",
                    extra={"session_id": self.session_id, "error": str(err)},
                )
        # The booked time counts from when the candidate hears the bot, not
        # from while the greeting audio was still being prepared.
        self._mark_interview_started()
        self.transcript_log.append(
            {
                "interaction_type": "greeting",
                "bot_speech": greeting,
                "candidate_answer": "",
            }
        )
        await self.speak(greeting)
        # No "let me know when you're ready": the candidate is already here
        # (and on camera), so the first question follows the greeting.
        await self._ask_next_question()

    async def candidate_joined(self) -> None:
        """The candidate joined (or spoke): start the interview if waiting and
        their camera is on; otherwise ask them to turn it on and keep waiting."""
        if not self.is_active or self.current_interaction_state != "waiting_for_candidate":
            return
        self._candidate_seen = True
        if not candidate_camera_on(self.session_id):
            self._start_camera_prompts()
            return
        self._cancel_candidate_wait()
        self.current_interaction_state = "idle"
        logger.info("Candidate joined; starting the interview", extra={"session_id": self.session_id})
        await self._greet()

    async def camera_frame_seen(self) -> None:
        """A participant's camera came on: start if it is the candidate's."""
        if (
            self._candidate_seen
            and self.current_interaction_state == "waiting_for_candidate"
            and candidate_camera_on(self.session_id)
        ):
            logger.info("Candidate's camera is on", extra={"session_id": self.session_id})
            await self.candidate_joined()

    def _start_camera_prompts(self) -> None:
        if self._camera_prompt_task is None or self._camera_prompt_task.done():
            logger.info(
                "Candidate is here but the camera is off; asking for it",
                extra={"session_id": self.session_id},
            )
            self._camera_prompt_task = asyncio.create_task(self._prompt_for_camera())

    async def _prompt_for_camera(self) -> None:
        while self.is_active and self.current_interaction_state == "waiting_for_candidate":
            # Not speak(): that switches the state to "speaking", and the bot
            # must stay "waiting_for_candidate" so the camera coming on (or the
            # wait running out) is still handled.
            logger.info("AI speaking", extra={"text": CAMERA_PROMPT_TEXT})
            if self.speech_output is not None:
                await self.speech_output(CAMERA_PROMPT_TEXT)
            await asyncio.sleep(CAMERA_PROMPT_INTERVAL_SECONDS)

    def _cancel_camera_prompts(self) -> None:
        task = self._camera_prompt_task
        if task and not task.done() and task is not asyncio.current_task():
            task.cancel()
        self._camera_prompt_task = None

    async def _wait_for_candidate(self) -> None:
        """Ask Attendee who is in the meeting every CANDIDATE_JOIN_POLL_SECONDS
        until the candidate joins; after CANDIDATE_JOIN_WAIT_SECONDS without
        them, leave the meeting as a no-show.

        The join webhook usually starts the interview first; polling covers a
        webhook that is lost or late (it travels through the public tunnel).
        """
        loop = asyncio.get_running_loop()
        deadline = loop.time() + CANDIDATE_JOIN_WAIT_SECONDS
        while self.current_interaction_state == "waiting_for_candidate":
            if await self._candidate_in_meeting_per_attendee():
                if not self._candidate_seen:
                    logger.info(
                        "Attendee lists the candidate in the meeting",
                        extra={"session_id": self.session_id},
                    )
                # Starts the interview, or (camera off) keeps asking for it.
                await self.candidate_joined()
                if self.current_interaction_state != "waiting_for_candidate":
                    return
            remaining = deadline - loop.time()
            if remaining <= 0:
                break
            await asyncio.sleep(min(CANDIDATE_JOIN_POLL_SECONDS, remaining))
        if self.current_interaction_state == "waiting_for_candidate":
            self._cancel_camera_prompts()
            camera_off = self._candidate_seen
            logger.info(
                "Candidate's camera stayed off; leaving the meeting as a no-show"
                if camera_off
                else "Candidate didn't join; leaving the meeting as a no-show",
                extra={"session_id": self.session_id, "wait_seconds": CANDIDATE_JOIN_WAIT_SECONDS},
            )
            self._status_note = (
                camera_not_on_note(CANDIDATE_JOIN_WAIT_SECONDS)
                if camera_off
                else candidate_did_not_join_note(CANDIDATE_JOIN_WAIT_SECONDS)
            )
            self._candidate_wait_task = None
            await self.end_interview("candidate_absent", leave_bot=True)

    async def _candidate_in_meeting_per_attendee(self) -> bool:
        """Replay Attendee's participant events for this bot; True when the
        candidate (recognised by name) is in the meeting now."""
        bot_id = self._session_bot_id()
        if bot_id is None:
            return False
        try:
            events = await attendee_client.list_participant_events(bot_id)
        except Exception as err:
            logger.warning(
                "Could not read the meeting's participants from Attendee",
                extra={"session_id": self.session_id, "bot_id": bot_id, "error": str(err)},
            )
            return is_candidate_present(self.session_id)
        if self._candidate_name is None:
            application_id = getattr(self.session, "application_id", None)
            self._candidate_name = (
                await interview_session_repo.get_candidate_name(application_id)
                if application_id
                else (None, None)
            )
        first_name, last_name = self._candidate_name
        for event in events:
            apply_participant_event(self.session_id, event, first_name, last_name)
        return is_candidate_present(self.session_id)

    def _cancel_candidate_wait(self):
        self._cancel_camera_prompts()
        task = self._candidate_wait_task
        if task and not task.done() and task is not asyncio.current_task():
            task.cancel()
        self._candidate_wait_task = None

    async def _warm_tts_cache(self) -> None:
        """Pre-synthesize all deterministic bot text for this session.

        Runs in the background starting right after questions are loaded, so
        by the time each question is actually asked its audio is already
        cached (see KokoroSynthesizer.warm). Never raises: a warm-up failure
        must fall back to normal on-demand synthesis, not break the session.
        """
        texts = known_bot_texts(self.questions, [getattr(self, "greeting_text", None)])
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
            self._cancel_candidate_wait()
            # Before any slow work: a runtime Attendee starts for this bot from
            # here on must not run (or end) the interview a second time.
            mark_interview_finished(self._session_bot_id())
            # The session row is reused if HR reschedules; start that attempt fresh.
            forget_session(self.session_id)
            self._save_question_awaiting_follow_up()
            # A candidate who never joined (or never said a word) is a no-show,
            # not a completed interview; HR reschedules those.
            no_show = not self._candidate_responded()
            if no_show:
                reason = "candidate_absent"
                self.termination_reason = reason
            await self.finalize(reason=reason)
            # The status endpoint has no termination-reason field yet; the
            # reason remains in this orchestration's durable finalization log.
            if self.api_client is not None:
                if no_show and self._status_note:
                    await self.api_client.update_status("no_show", note=self._status_note)
                elif no_show:
                    await self.api_client.update_status("no_show")
                else:
                    await self.api_client.update_status("completed")
            if leave_bot:
                await self._leave_bot_after_close()

    def _save_question_awaiting_follow_up(self) -> None:
        """The interview ended (silence, hang-up) before a follow-up was
        answered: score the question on its main answer, as _move_on does,
        instead of dropping an answer the candidate already gave."""
        pending = self._question_awaiting_follow_up
        self._question_awaiting_follow_up = None
        if pending is None or self.api_client is None:
            return
        question_obj, current_q = pending
        entry = next(
            (
                item
                for item in reversed(self.transcript_log)
                if item.get("interaction_type") == "question"
                and item.get("question_id") == question_obj.get("id")
            ),
            None,
        )
        primary_eval = entry.get("primary_eval") if entry else None
        if not primary_eval:
            return
        qa_entry, evaluation = build_completed_question_payload(
            question_obj=question_obj,
            current_q=current_q,
            transcript=entry.get("candidate_answer") or "",
            primary_eval=None,
            current_eval=primary_eval,
            question_number=self.current_question_idx + 1,
            follow_ups=_answered_follow_ups(entry.get("follow_ups")),
        )
        self.analysis_evaluations.append(evaluation)
        self._persist_question(qa_entry, evaluation)
        logger.info(
            "Saved a question whose follow-up was never answered",
            extra={"session_id": self.session_id, "question_id": question_obj.get("id")},
        )

    def _candidate_responded(self) -> bool:
        if self.analysis_evaluations:
            return True
        return any(
            isinstance(entry, dict) and str(entry.get("candidate_answer") or "").strip()
            for entry in self.transcript_log
        )

    async def abort_for_reschedule(self) -> None:
        """HR rescheduled this session while the bot was in the meeting.

        Stop without persisting anything: the session row now belongs to the
        new booking, so this attempt must not write a summary, transcript or
        status into it. Teardown's end_interview() becomes a no-op.
        """
        async with self._end_lock:
            if self._ending or self.is_finalized:
                return
            self._ending = True
            self.is_finalized = True
            self.termination_reason = "rescheduled"
            self.is_active = False
            self.current_interaction_state = "ending"
            self._cancel_inactivity_deadline()
            self._cancel_answer_settle()
            self._cancel_closing_reply_timeout()
            self._cancel_processing()
            self._cancel_filler_schedule()
            self._cancel_tts_warm()
            self._cancel_candidate_wait()
            mark_interview_finished(self._session_bot_id())
            # The session row is reused if HR reschedules; start that attempt fresh.
            forget_session(self.session_id)
        logger.info("Interview aborted for reschedule", extra={"session_id": self.session_id})

    async def fail_session(self, reason: str) -> None:
        """Mark the session failed and pull the bot out of the meeting.

        Used when the runtime cannot run the interview (e.g. TTS artifacts
        missing). Without this the bot stays in the call silently, which shows
        as a permanently muted participant.
        """
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
            self._cancel_candidate_wait()
            # The session row is reused if HR reschedules; start that attempt fresh.
            forget_session(self.session_id)
            logger.error(
                "Interview session failed; removing bot from meeting",
                extra={"session_id": self.session_id, "reason": reason},
            )
            if self.session is None:
                self.session = await interview_session_repo.get_by_id(self.session_id)
            if self.session is None:
                return
            mark_interview_finished(self._session_bot_id())
            if getattr(self.session, "status", None) == "failed":
                # Attendee reconnects while the bot is already being removed.
                return
            if self.api_client is None:
                self.api_client = SessionApiClient(session_id=str(self.session.id))
            # Status first, so the "left" webhook can't report it as completed;
            # then get the silent bot out before the slower persistence.
            await self.api_client.update_status("failed")
            await self._leave_bot_after_close()
            # Keep anything already answered before the failure.
            await self.finalize(reason=reason)

    async def cleanup(self):
        """Teardown connections, persisting the interview first if it ended early.

        Also asks the bot to leave: when the pipeline stops on its own (a
        crash, an idle timeout) the bot is still in the meeting and would sit
        there silently. If Attendee already dropped the call, the leave
        request just fails and is logged."""
        await self.end_interview("transport_disconnected", leave_bot=True)

    # ──────────────────────────── BACKGROUND PERSISTENCE ────────────────────────────

    def _persist_question(self, qa_entry: dict, evaluation: dict) -> None:
        """Save a finished question, then the conversation so far.

        The transcript used to be saved only when the interview ended, so a
        service restart mid-interview lost it, and the next runtime could not
        tell where the interview was (see _resume_saved_progress). Snapshot it
        now, before later turns change the entries; saved after the
        evaluation, so a question in the saved transcript has its score saved.
        """
        snapshot = normalize_interview_metadata(self.transcript_log)
        api_client = self.api_client

        async def save() -> None:
            # In order: an older snapshot landing last would drop questions.
            async with self._question_save_lock:
                await persist_qa_and_evaluation(api_client, qa_entry, evaluation)
                await api_client.save_interview_metadata(snapshot)

        self._schedule_persist(save())

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
        # The greeting only asks the candidate to say when they're ready, so a
        # short "Thank you." / "Yeah." there is a real reply, not noise.
        # Dropping it left the bot waiting and the questions never started.
        is_greeting_reply = (
            bool(self.transcript_log)
            and self.transcript_log[-1].get("interaction_type") == "greeting"
            and bool(transcript.strip())
        )
        if (
            is_probable_hallucination(transcript)
            and not is_closing_reply
            and not is_greeting_reply
        ):
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
        if self.current_interaction_state == "waiting_for_candidate":
            # Someone is talking. That starts the interview only if Attendee's
            # join events were missed, or the one non-host person present is
            # likely the candidate under another display name; never when only
            # the host / HR are in the meeting.
            if speech_may_start_interview(self.session_id):
                asyncio.create_task(self.candidate_joined())
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
        # Speech starting cancelled the pending settle. If this stretch of
        # speech then transcribes to nothing usable (noise, "Thank you."),
        # no new transcript re-arms it and what was already collected would
        # never be processed: the bot went silent mid-interview.
        if (
            self.current_interaction_state == "collecting_answer"
            and self._answer_buffer
            and (self._answer_settle_task is None or self._answer_settle_task.done())
        ):
            # Allow time for this speech's transcript first: if one arrives,
            # handle_candidate_speech restarts the settle as usual.
            self._answer_settle_task = asyncio.create_task(
                self._process_after_answer_settles(stt_grace_seconds=STT_RESULT_GRACE_SECONDS)
            )

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

    def _awaiting_greeting_reply(self) -> bool:
        """The greeting was said and the candidate hasn't replied at all yet."""
        return (
            self.current_interaction_state == "listening"
            and bool(self.transcript_log)
            and self.transcript_log[-1].get("interaction_type") == "greeting"
            and not self.transcript_log[-1].get("candidate_answer")
            and not self._answer_buffer
        )

    async def _end_after_inactivity(self):
        """Prompt twice, then end after a third unanswered 30-second window."""
        try:
            while self.is_active:
                cycle_started_at = self._inactivity_cycle_started_at
                if cycle_started_at is None:
                    return
                awaiting_greeting_reply = self._awaiting_greeting_reply()
                window = (
                    GREETING_REPLY_TIMEOUT_SECONDS
                    if awaiting_greeting_reply
                    else SILENCE_PROMPT_SECONDS
                )
                remaining = window - (
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
                if awaiting_greeting_reply:
                    # Bug-029: start the interview rather than waiting on a
                    # candidate who hasn't said they're ready.
                    logger.info(
                        "No reply to the greeting; starting the questions",
                        extra={"session_id": self.session_id},
                    )
                    await self.speak(START_WITHOUT_REPLY_TEXT)
                    await self._ask_next_question()
                    return
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

    async def _process_after_answer_settles(self, stt_grace_seconds: float = 0.0):
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
        # A skip request moves on at once; "one moment" before it is noise.
        if not is_skip_request(" ".join(part for part in self._answer_buffer if part)):
            self._start_filler_schedule()
        try:
            await asyncio.sleep(stt_grace_seconds + ANSWER_SETTLE_SECONDS)
            if not self.is_active or self.current_interaction_state != "collecting_answer":
                return
            if self._candidate_speaking:
                # They started talking again before the previous sentence
                # finished transcribing; replying now talks over them.
                # handle_candidate_speech_stopped re-arms the settle.
                return
            transcript = " ".join(part for part in self._answer_buffer if part).strip()
            if not transcript:
                return
            if looks_unfinished(transcript):
                # "...the third point is" — the candidate is mid-thought.
                # Give them longer before answering (Bug-042), and hold any
                # filler until the real wait for the reply starts.
                logger.info(
                    "Answer looks unfinished; waiting longer",
                    extra={"session_id": self.session_id, "transcript_tail": transcript[-60:]},
                )
                self._cancel_filler_schedule()
                await asyncio.sleep(UNFINISHED_ANSWER_EXTRA_SECONDS)
                if not self.is_active or self.current_interaction_state != "collecting_answer":
                    return
                if self._candidate_speaking:
                    return
                transcript = " ".join(part for part in self._answer_buffer if part).strip()
                self._turn_started_at = asyncio.get_running_loop().time()
                self._start_filler_schedule()
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

        if is_skip_request(transcript):
            # "Skip this question" / "next question" / "I don't know": move
            # on without asking the LLM, which only treated a skip as such if
            # the candidate also said they didn't know (Bug-039).
            self._cancel_filler_schedule()
            await self._move_on(
                question_obj, current_q, transcript, primary_eval_data, reason="skip_request"
            )
            return

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
            prior = (
                self.transcript_log[-1].get("conversational_turns", [])
                if self.transcript_log
                else []
            )
            prior_non_answers = sum(1 for turn in prior if turn.get("intent") == "SMALL_TALK")
            if len(prior) >= MAX_CONVERSATIONAL_TURNS_PER_QUESTION or (
                intent == "SMALL_TALK"
                and prior_non_answers >= MAX_NON_ANSWER_REASKS_PER_QUESTION
            ):
                # "Wonderful." / "Thank you." / "Yes." — re-asking the same
                # question again just loops (Bug-039).
                await self._move_on(
                    question_obj, current_q, transcript, primary_eval_data,
                    reason="no_answer_after_prompts",
                )
                return
            await self._handle_conversational(
                transcript, result.get("response", ""), intent=intent
            )
            return

        if intent == "SKIP":
            await self._move_on(
                question_obj, current_q, transcript, primary_eval_data, reason="skip_intent"
            )
            return

        await self._handle_answer(question_obj, current_q, transcript, result, primary_eval_data)

    # ──────────────────────────── INTENT HANDLERS ────────────────────────────

    async def _handle_conversational(
        self, transcript: str, ai_response: str, *, intent: str = "SMALL_TALK"
    ):
        """Handles CLARIFICATION and SMALL_TALK intents."""
        if not ai_response or not str(ai_response).strip():
            ai_response = "Okay, sounds good."

        if self.transcript_log:
            self.transcript_log[-1].setdefault("conversational_turns", []).append(
                {
                    "candidate_speech": transcript,
                    "ai_response": ai_response,
                    "intent": intent,
                }
            )

        await self.speak(ai_response)
        # A request for time is still a response turn. Never leave a session
        # indefinitely waiting after conversational speech.
        self._begin_listening()

    async def _move_on(
        self,
        question_obj: dict,
        current_q: str,
        transcript: str,
        primary_eval_data: Optional[dict],
        *,
        reason: str,
    ):
        """Tell the candidate we're moving on, then go to the next question.

        During a follow-up the main answer was already evaluated, so the
        question is completed with that evaluation instead of a zero score.
        """
        logger.info(
            "Moving on to the next question",
            extra={"session_id": self.session_id, "reason": reason},
        )
        # Said just before the next question, not here: if this answer ends
        # the interview (early stop, time limit) the bot goes straight to
        # the closing instead of promising a next question.
        self._pending_transition_text = MOVE_ON_TEXT
        if primary_eval_data is not None:
            # The follow-up went unanswered; _complete_question leaves it out
            # of the Q&A save but it stays in the transcript.
            await self._complete_question(
                question_obj, current_q, transcript, None, primary_eval_data
            )
        else:
            await self._handle_skip(question_obj, current_q, transcript)

    async def _handle_skip(self, question_obj: dict, current_q: str, transcript: str):
        """Handles SKIP intent — saves 0-score evaluation and moves on.

        analysis_evaluations is updated synchronously (routing reads it right
        after this returns); the Core API save runs in the background.
        """
        self._question_awaiting_follow_up = None
        if self.transcript_log:
            self.transcript_log[-1]["candidate_answer"] = transcript

        qa_entry = AnswerEvaluator.build_qa_entry(question_obj, current_q, transcript, self.current_question_idx + 1)
        skip_eval = AnswerEvaluator.build_skip_evaluation(question_obj, transcript, self.current_question_idx + 1)
        self.analysis_evaluations.append(skip_eval)
        self._persist_question(qa_entry, skip_eval)

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
        # Acknowledge only a finished answer, and not on top of a filler the
        # candidate just heard ("One moment... Thank you for answering...").
        if decision == "NEXT_QUESTION" and not self._filler_spoken_this_turn:
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
        # No follow-up on the final question asked in the last minutes.
        if (
            len(current_follow_ups) >= MAX_FOLLOW_UPS_PER_QUESTION or self._final_question_asked
        ) and not is_complete:
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
            self._question_awaiting_follow_up = (question_obj, current_q)
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
        self._question_awaiting_follow_up = None
        if self.transcript_log and not self.transcript_log[-1].get("candidate_answer"):
            self.transcript_log[-1]["candidate_answer"] = transcript

        follow_ups = (
            _answered_follow_ups(self.transcript_log[-1].get("follow_ups"))
            if self.transcript_log
            else None
        )
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
        self._persist_question(qa_entry, evaluation)

        self.current_question_idx += 1
        await self._ask_next_question()

    # ──────────────────────────── QUESTION FLOW ────────────────────────────

    async def _ask_next_question(self):
        """Moves to the next question or closes the interview."""
        if not hasattr(self, "question_queues"):
            from src.screening_pipeline.routing_engine import initialize_queues
            self.question_queues = initialize_queues(self.questions)
            
        from src.screening_pipeline.routing_engine import CORE_SEQUENCE, get_next_question

        # After the compulsory questions, no new question near the end of the
        # booked time: close on time instead of running over.
        question_obj, termination_reason = None, None
        if len(self.analysis_evaluations) >= len(CORE_SEQUENCE) and self._out_of_time():
            question_obj = self._final_question()
            if question_obj is None:
                logger.info(
                    "Booked interview time is up; closing",
                    extra={"session_id": self.session_id, "minutes": self._interview_minutes()},
                )
                self.termination_reason = "time_limit"
                self._pending_transition_text = None
                await self._close_interview()
                return
            logger.info(
                "Last minutes of the booked time; asking one final question",
                extra={"session_id": self.session_id, "category": question_obj.get("category")},
            )

        if question_obj is None:
            question_obj, termination_reason = get_next_question(self.question_queues, self.analysis_evaluations)
        
        if not question_obj:
            if termination_reason == "fatal_failure":
                logger.info("Candidate failed to recover. Terminating early.", extra={"session_id": self.session_id})
                self.termination_reason = "fatal_failure"
            elif termination_reason in ("not_eligible", "not_eligible_early"):
                from src.screening_pipeline.routing_engine import core_phase_score

                logger.info(
                    "Compulsory questions scored below the bar; ending early",
                    extra={
                        "session_id": self.session_id,
                        "core_score": core_phase_score(self.analysis_evaluations),
                    },
                )
                self.termination_reason = termination_reason
            self._pending_transition_text = None
            await self._close_interview()
            return

        transition = self._pending_transition_text
        self._pending_transition_text = None
        if transition:
            await self.speak(transition)

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

    def _session_bot_id(self) -> Optional[str]:
        metadata = getattr(self.session, "interview_metadata", None)
        bot_id = metadata.get("bot_id") if isinstance(metadata, dict) else None
        return bot_id.strip() if isinstance(bot_id, str) and bot_id.strip() else None

    async def _leave_bot_after_close(self):
        """Ask Attendee to leave after the closing reply has been persisted."""
        bot_id = self._session_bot_id()
        if bot_id is None:
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

    def stt_prompt(self) -> str | None:
        """Context for transcribing the candidate's current answer.

        Whisper treats its prompt as preceding text and favours its spelling,
        so the question and its expected keywords make technical terms come
        out right ("ConcurrentHashMap", not "Concrete Hotsmap"). Keywords go
        last because Whisper keeps only the end of a long prompt.
        """
        question_obj = getattr(self, "current_question_obj", None) or {}
        question = str(question_obj.get("question") or "").strip()
        if not question:
            return None
        parts = [question]
        skill = str(question_obj.get("skill_focus") or "").strip()
        keywords = [str(k).strip() for k in question_obj.get("expected_keywords") or [] if str(k).strip()]
        terms = ([skill] if skill else []) + keywords
        if terms:
            parts.append("Key terms: " + ", ".join(terms) + ".")
        return " ".join(parts)

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
        self._filler_spoken_this_turn = True
        await self.speech_output(text)

    def _start_filler_schedule(self) -> None:
        """Arm the filler schedule for this turn. See _run_filler_schedule."""
        self._cancel_filler_schedule()
        self._filler_spoken_this_turn = False
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
