"""Pipecat runtime bridge for one Attendee screening session."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Callable

from pipecat.frames.frames import (
    Frame,
    InputAudioRawFrame,
    InterruptionFrame,
    StartFrame,
    TranscriptionFrame,
    TTSSpeakFrame,
)
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from src.core.config import settings
from src.core.logger import logger
from src.screening_pipeline.interview_policy import InterviewPolicy
from src.screening_pipeline.orchestrator import InterviewOrchestrator
from src.screening_pipeline.pipecat_transport import (
    AttendeeOutputProcessor,
    SpeechCompleteFrame,
)
from src.screening_pipeline.pipecat_tts import KokoroTTSService
from src.screening_pipeline.stt_client import WhisperCloudSTTClient


class AttendeeInputProcessor(FrameProcessor):
    """Accept decoded Attendee PCM and inject it into a Pipecat pipeline."""

    def __init__(self):
        super().__init__(name="attendee-input")
        self.ready = asyncio.Event()

    async def push_audio(self, pcm_bytes: bytes, sample_rate: int) -> None:
        if not self.ready.is_set():
            return
        await self.push_frame(
            InputAudioRawFrame(
                audio=pcm_bytes,
                sample_rate=sample_rate,
                num_channels=1,
            ),
            FrameDirection.DOWNSTREAM,
        )

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, StartFrame):
            self.ready.set()
        await self.push_frame(frame, direction)


class ExistingWhisperProcessor(FrameProcessor):
    """Bridge the existing WebRTC-VAD/HTTP-Whisper client into Pipecat frames."""

    def __init__(
        self,
        stt_client: WhisperCloudSTTClient,
        on_speech_start: Callable[[], None] | None = None,
        session_id: str | None = None,
    ):
        super().__init__(name="existing-whisper")
        self.stt_client = stt_client
        self.on_speech_start = on_speech_start
        self.session_id = session_id
        self.stt_client.on_transcript = self._on_transcript
        self.stt_client.on_speech_start = self._on_speech_start

    def _on_speech_start(self) -> None:
        if self.on_speech_start is not None:
            self.on_speech_start()
        asyncio.create_task(
            self.push_frame(InterruptionFrame(), FrameDirection.DOWNSTREAM)
        )

    def _on_transcript(self, transcript: str) -> None:
        # Log at the STT-to-Pipecat boundary so speech remains visible even if
        # policy state later rejects it (for example, while the bot is speaking).
        logger.info(
            "Pipecat candidate transcript received",
            extra={"session_id": self.session_id, "transcript": transcript},
        )
        asyncio.create_task(
            self.push_frame(
                TranscriptionFrame(
                    text=transcript,
                    user_id="candidate",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    finalized=True,
                ),
                FrameDirection.DOWNSTREAM,
            )
        )

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, InputAudioRawFrame):
            await self.stt_client.send_audio(frame.audio, frame.sample_rate)
            return
        await self.push_frame(frame, direction)


class InterviewPolicyProcessor(FrameProcessor):
    """Send final transcripts to EZScreen policy and policy speech to TTS."""

    def __init__(
        self,
        policy: InterviewPolicy,
        register_speech_event: Callable[[asyncio.Event], None] | None = None,
    ):
        super().__init__(name="interview-policy")
        self.policy = policy
        self.register_speech_event = register_speech_event
        self._current_speech_event: asyncio.Event | None = None

    async def speak(self, text: str) -> None:
        done_event = asyncio.Event()
        self._current_speech_event = done_event
        # Register before the utterance enters TTS, so an interruption that
        # arrives before the completion marker can unblock the policy.
        if self.register_speech_event is not None:
            self.register_speech_event(done_event)
        await self.push_frame(TTSSpeakFrame(text), FrameDirection.DOWNSTREAM)
        await self.push_frame(SpeechCompleteFrame(done_event), FrameDirection.DOWNSTREAM)
        try:
            await done_event.wait()
        finally:
            if self._current_speech_event is done_event:
                self._current_speech_event = None

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, InterruptionFrame):
            if self._current_speech_event is not None and not self._current_speech_event.is_set():
                self._current_speech_event.set()
        elif isinstance(frame, TranscriptionFrame):
            if frame.finalized:
                self.policy.handle_candidate_speech(frame.text)
            return
        await self.push_frame(frame, direction)


class PipecatInterviewRuntime:
    """Own one Pipecat pipeline while delegating interview policy to EZScreen."""

    def __init__(self, websocket, session_id: str):
        self.websocket = websocket
        self.session_id = session_id
        self.input = AttendeeInputProcessor()
        self.stt_client = WhisperCloudSTTClient(
            api_url=settings.whisper_api_url,
            api_key=settings.whisper_api_key,
            on_transcript=lambda _transcript: None,
        )
        self.policy = InterviewOrchestrator(
            session_id=session_id,
            websocket=websocket,
            stt_client=self.stt_client,
        )
        self.whisper = ExistingWhisperProcessor(
            self.stt_client,
            on_speech_start=self.policy.handle_candidate_activity,
            session_id=self.session_id,
        )
        self.tts = KokoroTTSService()
        self.output = AttendeeOutputProcessor(websocket)
        self.policy_processor = InterviewPolicyProcessor(
            self.policy,
            register_speech_event=self.output.register_speech_event,
        )
        self.policy.speech_output = self.policy_processor.speak
        self.pipeline = Pipeline(
            [self.input, self.whisper, self.policy_processor, self.tts, self.output]
        )
        self.task = PipelineTask(
            self.pipeline,
            params=PipelineParams(
                audio_in_sample_rate=24000,
                audio_out_sample_rate=24000,
            ),
        )
        self.runner: PipelineRunner | None = None

    async def run(self) -> None:
        """Start the pipeline and then begin the existing greeting flow."""
        logger.info("Pipecat runtime starting", extra={"session_id": self.session_id})
        await self.tts.validate_ready()
        logger.info("Pipecat Kokoro ready", extra={"session_id": self.session_id})
        self.runner = PipelineRunner()
        runner_task = asyncio.create_task(self.runner.run(self.task))
        ready_task = asyncio.create_task(self.input.ready.wait())
        try:
            done, pending = await asyncio.wait(
                [ready_task, runner_task],
                timeout=20.0,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if ready_task not in done:
                raise TimeoutError("Pipecat pipeline ready timeout")

            if runner_task in done:
                if runner_task.cancelled():
                    raise RuntimeError("Pipecat runner was cancelled before pipeline became ready")
                exc = runner_task.exception()
                if exc:
                    raise exc
                raise RuntimeError("Pipecat runner stopped before pipeline became ready")

            logger.info(
                "Pipecat pipeline ready",
                extra={"session_id": self.session_id},
            )
            await self.policy.start()
            await runner_task
        except Exception:
            if not runner_task.done():
                runner_task.cancel()
                await asyncio.gather(runner_task, return_exceptions=True)
            logger.exception(
                "Pipecat runtime failed",
                extra={"session_id": self.session_id},
            )
            raise
        finally:
            if not ready_task.done():
                ready_task.cancel()
            await self.policy.cleanup()

    async def push_audio(self, pcm_bytes: bytes, sample_rate: int) -> None:
        await self.input.push_audio(pcm_bytes, sample_rate)

    async def cleanup(self) -> None:
        if self.policy_processor._current_speech_event is not None:
            self.policy_processor._current_speech_event.set()
        await self.policy.cleanup()
        await self.stt_client.close()
        await self.task.cancel(reason="session_cleanup")
