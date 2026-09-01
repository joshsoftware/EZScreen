"""
Interview Orchestrator — Main state machine for the AI screening interview.
Controls the flow: Greeting → Questions → Evaluation → Follow-up → Closing.
"""
import asyncio
import random
import json
from typing import Any
from src.core.logger import logger
from src.core.config import settings
from src.meeting_bot.repository import interview_session_repo
from src.screening_pipeline.stt_client import WhisperCloudSTTClient
from src.screening_pipeline.tts_client import KokoroCloudTTSClient
from src.screening_pipeline.evaluator import AnswerEvaluator
from src.screening_pipeline.session_api import SessionApiClient
from src.screening_pipeline.prompts import (
    GREETING_TEXT,
    CLOSING_TEXT,
    MAX_FOLLOW_UPS_PER_QUESTION,
)
from src.llm.client import OllamaClient


class InterviewOrchestrator:
    """
    Manages the state machine for the AI interview.
    Coordinates STT, Intent Router, LLM Evaluator, TTS, and Core-API persistence.
    """

    def __init__(self, bot_id: str, websocket):
        self.bot_id = bot_id
        self.websocket = websocket
        self.session: Any = None
        self.questions: list = []
        self.current_question_idx = 0
        self.is_active = False

        # Audio clients
        self.stt_client = WhisperCloudSTTClient(
            api_url=settings.whisper_api_url,
            api_key=settings.whisper_api_key,
            on_transcript=self.handle_candidate_speech
        )
        self.tts_client = KokoroCloudTTSClient(
            api_url=settings.kokoro_api_url,
            api_key=settings.kokoro_api_key
        )

        # AI modules
        llm_client = OllamaClient()
        self.evaluator = AnswerEvaluator(llm_client)
        self.api_client: SessionApiClient = None  # Initialized after session is loaded

        # State tracking
        self.current_interaction_state = "idle"  # idle, speaking, listening, evaluating
        self.transcript_log: list = []
        self.analysis_evaluations: list = []

    # ──────────────────────────── LIFECYCLE ────────────────────────────

    async def start(self):
        """Initializes the interview session and speaks the greeting."""
        logger.info("Orchestrator starting", extra={"bot_id": self.bot_id})
        self.session = await interview_session_repo.get_by_bot_id(self.bot_id)

        if not self.session:
            logger.error("No session found for bot. Cannot start interview.", extra={"bot_id": self.bot_id})
            return

        # Initialize the API client with the real session ID
        self.api_client = SessionApiClient(session_id=str(self.session.id))

        # Fetch questions and randomize their order
        self.questions = self.session.generated_questions or []
        random.shuffle(self.questions)
        self.is_active = True

        await self.stt_client.connect()

        # Greeting
        self.transcript_log.append({
            "interaction_type": "greeting",
            "bot_speech": GREETING_TEXT,
            "candidate_answer": ""
        })
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

        logger.info("Candidate speech received", extra={"transcript": transcript})
        self.current_interaction_state = "evaluating"
        asyncio.create_task(self._process_speech(transcript))

    # ──────────────────────────── MAIN PROCESSING ────────────────────────────

    async def _process_speech(self, transcript: str):
        """Routes the candidate's speech through intent detection and evaluation."""

        # If candidate is responding to the greeting, just move to first question
        if self.transcript_log and self.transcript_log[-1].get("interaction_type") == "greeting":
            self.transcript_log[-1]["candidate_answer"] = transcript
            await self._ask_next_question()
            return

        question_obj = self.questions[self.current_question_idx]
        current_q = question_obj.get("question", "")

        # ── Step 1: Intent Routing ──
        intent, ai_response = await self.evaluator.route_intent(current_q, transcript)

        if intent in ["CLARIFICATION", "SMALL_TALK"]:
            await self._handle_conversational(transcript, ai_response)
            return

        if intent == "SKIP":
            await self._handle_skip(question_obj, current_q, transcript)
            return

        # ── Step 2: Answer Evaluation ──
        await self._handle_answer(question_obj, current_q, transcript)

    # ──────────────────────────── INTENT HANDLERS ────────────────────────────

    async def _handle_conversational(self, transcript: str, ai_response: str):
        """Handles CLARIFICATION and SMALL_TALK intents."""
        if not ai_response.strip():
            ai_response = "Okay, sounds good."

        if self.transcript_log:
            self.transcript_log[-1].setdefault("follow_ups", []).append({
                "candidate_speech": transcript,
                "ai_response": ai_response
            })

        await self.speak(ai_response)
        self.current_interaction_state = "listening"

    async def _handle_skip(self, question_obj: dict, current_q: str, transcript: str):
        """Handles SKIP intent — saves 0-score evaluation and moves on."""
        if self.transcript_log:
            self.transcript_log[-1]["candidate_answer"] = transcript

        # Save clean Q&A transcript
        qa_entry = AnswerEvaluator.build_qa_entry(question_obj, current_q, transcript)
        await self.api_client.save_transcript(qa_entry)

        # Save 0-score evaluation
        skip_eval = AnswerEvaluator.build_skip_evaluation(question_obj, transcript)
        self.analysis_evaluations.append(skip_eval)
        await self.api_client.save_evaluation(skip_eval)

        self.current_question_idx += 1
        await self._ask_next_question()

    async def _handle_answer(self, question_obj: dict, current_q: str, transcript: str):
        """Handles ANSWERING intent — evaluates and decides follow-up or next question."""

        # Determine keywords: use missing keywords from primary eval for follow-up
        primary_eval_data = None
        if self.transcript_log and self.transcript_log[-1].get("primary_eval"):
            primary_eval_data = self.transcript_log[-1]["primary_eval"]
            expected_keywords = ", ".join(primary_eval_data.get("keywords_missing", []))
            answer_depth = "partial_depth"
        else:
            expected_keywords = ", ".join(question_obj.get("expected_keywords", []))
            answer_depth = question_obj.get("answer_depth", "partial_depth")

        # Get follow-up context if exists
        follow_up_context = None
        if self.transcript_log and self.transcript_log[-1].get("follow_ups"):
            follow_up_context = self.transcript_log[-1]["follow_ups"]

        # Evaluate answer via LLM
        eval_data = await self.evaluator.evaluate_answer(
            current_question=current_q,
            transcript=transcript,
            expected_keywords=expected_keywords,
            answer_depth=answer_depth,
            follow_up_context=follow_up_context
        )

        decision = eval_data.get("decision", "NEXT_QUESTION")
        is_complete = (decision == "NEXT_QUESTION")
        follow_up_question = eval_data.get("suggested_follow_up", "")

        if decision == "REPEAT_QUESTION":
            is_complete = False
            follow_up_question = "I'm sorry, could you please repeat your answer?"

        # Enforce follow-up limit
        current_follow_ups = self.transcript_log[-1].get("follow_ups", []) if self.transcript_log else []
        if len(current_follow_ups) >= MAX_FOLLOW_UPS_PER_QUESTION and not is_complete:
            logger.info("Follow-up limit reached, forcing completion")
            is_complete = True
            follow_up_question = ""

        if not is_complete and follow_up_question:
            # Ask follow-up question
            if self.transcript_log:
                self.transcript_log[-1]["primary_eval"] = eval_data
                self.transcript_log[-1].setdefault("follow_ups", []).append({
                    "candidate_speech": transcript,
                    "ai_response": follow_up_question
                })
            await self.speak(follow_up_question)
            self.current_interaction_state = "listening"
        else:
            # Question complete — persist to DB
            await self._complete_question(question_obj, current_q, transcript, primary_eval_data, eval_data)

    async def _complete_question(
        self, question_obj: dict, current_q: str, transcript: str,
        primary_eval: dict, current_eval: dict
    ):
        """Saves the completed question's transcript and evaluation to core-api."""
        if self.transcript_log:
            self.transcript_log[-1]["candidate_answer"] = transcript

        follow_ups = self.transcript_log[-1].get("follow_ups") if self.transcript_log else None

        # Save clean Q&A transcript (with nested follow-ups)
        qa_entry = AnswerEvaluator.build_qa_entry(question_obj, current_q, transcript, follow_ups)
        await self.api_client.save_transcript(qa_entry)

        # Save evaluation (with nested follow-up scores)
        evaluation = AnswerEvaluator.build_evaluation_block(
            question_obj, current_q, transcript,
            primary_eval, current_eval, follow_ups
        )
        self.analysis_evaluations.append(evaluation)
        await self.api_client.save_evaluation(evaluation)

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

        self.transcript_log.append({
            "interaction_type": "question",
            "question_id": question_obj.get("id"),
            "bot_speech": q_text,
            "candidate_answer": "",
            "follow_ups": []
        })

        await self.speak(q_text)
        self.current_interaction_state = "listening"

    async def _close_interview(self):
        """Speaks closing message and saves the final summary."""
        self.transcript_log.append({
            "interaction_type": "closing",
            "bot_speech": CLOSING_TEXT,
            "candidate_answer": ""
        })

        # Calculate and persist final_summary
        await self.api_client.save_final_summary(self.analysis_evaluations)
        
        # Persist the complete conversational transcript
        await self.api_client.save_interview_metadata(self.transcript_log)

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
