import asyncio
from typing import Dict, Any
from src.core.logger import logger
from src.meeting_bot.repository import interview_session_repo
from src.screening_pipeline.stt_client import DeepgramSTTClient
from src.screening_pipeline.tts_client import TTSClient
from src.core.config import settings

class InterviewOrchestrator:
    """
    Manages the state machine for the AI interview.
    Controls the STT, Intent Router, LLM Evaluator, and TTS modules.
    """
    
    def __init__(self, bot_id: str, websocket):
        self.bot_id = bot_id
        self.websocket = websocket
        self.session: Any = None
        self.questions: list = []
        self.current_question_idx = 0
        self.is_active = False
        
        self.stt_client = DeepgramSTTClient(
            api_key=settings.deepgram_api_key,
            on_transcript=self.handle_candidate_speech
        )
        self.tts_client = TTSClient(api_key=settings.tts_api_key or "")
        
        # State tracking for the Q&A loop
        self.current_interaction_state = "idle" # idle, speaking, listening, evaluating
        self.transcript_log: list = []

    async def append_transcript_to_db(self, interaction: Dict[str, Any]):
        """Makes an internal call to core-api to append a single interaction to the DB."""
        import httpx
        from src.core.config import settings
        
        try:
            url = f"{settings.core_api_url.rstrip('/')}/api/v1/interview-sessions/{self.session.id}/transcript"
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(url, json=interaction)
                if resp.status_code not in (200, 201, 204):
                    logger.error("Failed to incrementally save transcript", extra={"status": resp.status_code})
        except Exception as err:
            logger.error("Error communicating with core-api to save transcript", extra={"error": str(err)})

    async def start(self):
        """Initializes the interview session and speaks the greeting."""
        logger.info(f"Orchestrator starting for bot {self.bot_id}")
        self.session = await interview_session_repo.get_by_bot_id(self.bot_id)
        
        # MOCK FALLBACK FOR LOCAL TESTING VIA test_websocket.py
        if not self.session and self.bot_id == "test_bot_123":
            logger.warning("Using mock session for local test_websocket.py execution!")
            class MockSession:
                id = "00000000-0000-0000-0000-000000000000"
                generated_questions = [
                    {"id": 1, "question": "Mock question 1: Can you explain HashMap?"}, 
                    {"id": 2, "question": "Mock question 2: What is Docker?"}
                ]
            self.session = MockSession()
            
        if not self.session:
            logger.error("Could not find session for bot", extra={"bot_id": self.bot_id})
            return
            
        # Fetch the pre-generated questions and randomize their order
        import random
        self.questions = self.session.generated_questions or []
        random.shuffle(self.questions)
        
        self.is_active = True
        
        await self.stt_client.connect()
        
        # 1. State 1: The Start (greeting)
        greeting_text = "Hello! I'm your AI interviewer today. Let's begin with a few technical questions."
        interaction = {
            "interaction_type": "greeting",
            "bot_speech": greeting_text,
            "candidate_answer": ""
        }
        self.transcript_log.append(interaction)
        await self.append_transcript_to_db(interaction)
        
        await self.speak(greeting_text)
        self.current_interaction_state = "listening"

    def handle_candidate_speech(self, transcript: str):
        """Callback from STT when the candidate finishes a thought."""
        if not self.is_active or self.current_interaction_state != "listening":
            return
            
        logger.info(f"Candidate said: {transcript}")
        self.current_interaction_state = "evaluating"
        
        # We spawn an async task so we don't block the STT thread
        asyncio.create_task(self.process_intent_and_evaluate(transcript))

    async def process_intent_and_evaluate(self, transcript: str):
        """
        Runs the text through the Intent Router, and either evaluates it 
        or handles it conversationally (clarifications, small talk).
        """
        logger.debug("Routing intent...")
        
        # TODO: Call Gemma4:31b Intent Router here
        intent = "ANSWERING" # Mocked intent
        
        if intent == "ANSWERING":
            # Record the answer in the transcript log
            if self.transcript_log:
                self.transcript_log[-1]["candidate_answer"] = transcript
                # Re-sync the completed interaction block to the DB
                await self.append_transcript_to_db(self.transcript_log[-1])
                
            # TODO: Call Gemma4:31b Evaluation prompt
            
            # For now, just move to next question
            self.current_question_idx += 1
            await self.ask_next_question()
            
        elif intent in ["CLARIFICATION", "SMALL_TALK"]:
            # TODO: Add follow_up object to transcript_log, synthesize bot_response
            pass
            
        elif intent == "SKIP":
            self.current_question_idx += 1
            await self.ask_next_question()

    async def ask_next_question(self):
        """Moves to the next question in the array or closes the interview."""
        if self.current_question_idx >= len(self.questions):
            # State 4: The End (closing)
            closing_text = "Thank you for your time today. Our HR team will be in touch shortly."
            interaction = {
                "interaction_type": "closing",
                "bot_speech": closing_text,
                "candidate_answer": ""
            }
            self.transcript_log.append(interaction)
            await self.append_transcript_to_db(interaction)
            
            await self.speak(closing_text)
            self.current_interaction_state = "closing"
            # We don't need a massive bulk save anymore! Just call Attendee leave_bot here.
            return

        question_obj = self.questions[self.current_question_idx]
        q_text = question_obj.get("question", "")
        
        # State 2: Asking from the List
        interaction = {
            "interaction_type": "question",
            "question_id": question_obj.get("id"),
            "bot_speech": q_text,
            "candidate_answer": "",
            "follow_ups": []
        }
        self.transcript_log.append(interaction)
        await self.append_transcript_to_db(interaction)
        
        await self.speak(q_text)
        self.current_interaction_state = "listening"

    async def speak(self, text: str):
        """Synthesizes text and streams it to the WebSocket."""
        self.current_interaction_state = "speaking"
        from src.screening_pipeline.audio_websocket import speak_to_attendee
        
        async for chunk in self.tts_client.synthesize(text):
            # If candidate barged in, we would break this loop
            if not self.is_active:
                break
            await speak_to_attendee(self.websocket, chunk)

    async def cleanup(self):
        """Teardown connections."""
        self.is_active = False
        await self.stt_client.close()
