"""Pipecat runtime bridge for one Attendee screening session."""

from __future__ import annotations

import asyncio
import audioop
from typing import Callable

from pipecat.frames.frames import (
    Frame,
    InputAudioRawFrame,
    InterruptionFrame,
    StartFrame,
    TranscriptionFrame,
    TTSSpeakFrame,
    VADUserStartedSpeakingFrame,
)
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.processors.audio.vad_processor import VADProcessor

from src.core.logger import logger
from src.screening_pipeline.interview_policy import InterviewPolicy
from src.screening_pipeline.pipecat_policy import PipecatInterviewPolicy
from src.screening_pipeline.pipecat_stt import WhisperHttpSTTService
from src.screening_pipeline.pipecat_transport import (
    AttendeeOutputProcessor,
    SpeechCompleteFrame,
)
from src.screening_pipeline.pipecat_tts import KokoroTTSService

SCREENING_TURN_END_SILENCE_SECONDS = 2.0


class AttendeeInputProcessor(FrameProcessor):
    """Accept decoded Attendee PCM and inject it into a Pipecat pipeline."""

    def __init__(self):
        super().__init__(name="attendee-input")
        self.ready = asyncio.Event()

    async def push_audio(self, pcm_bytes: bytes, sample_rate: int) -> None:
        if not self.ready.is_set():
            return
        sample_rate = int(sample_rate)
        if sample_rate != 16000:
            pcm_bytes, _state = audioop.ratecv(
                pcm_bytes, 2, 1, sample_rate, 16000, None
            )
        await self.push_frame(
            InputAudioRawFrame(
                audio=pcm_bytes,
                sample_rate=16000,
                num_channels=1,
            ),
            FrameDirection.DOWNSTREAM,
        )

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, StartFrame):
            self.ready.set()
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
        elif isinstance(frame, VADUserStartedSpeakingFrame):
            self.policy.handle_candidate_activity()
            # Candidate speech is authoritative in a screening interview.
            # Interrupt bot audio so the entire response can be captured rather
            # than dropping a transcript that arrives while policy is speaking.
            await self.push_frame(InterruptionFrame(), FrameDirection.DOWNSTREAM)
        elif isinstance(frame, TranscriptionFrame):
            if frame.finalized:
                self.policy.handle_candidate_speech(frame.text)
            return
        await self.push_frame(frame, direction)


class PipecatInterviewRuntime:
    """Own one Pipecat pipeline for a complete Attendee screening session."""

    def __init__(self, websocket, session_id: str):
        self.websocket = websocket
        self.session_id = session_id
        self.input = AttendeeInputProcessor()
        self.policy = PipecatInterviewPolicy(
            session_id=session_id,
        )
        self.vad = VADProcessor(
            vad_analyzer=SileroVADAnalyzer(
                sample_rate=16000,
                params=VADParams(stop_secs=SCREENING_TURN_END_SILENCE_SECONDS),
            )
        )
        self.stt = WhisperHttpSTTService(sample_rate=16000)
        self.tts = KokoroTTSService()
        self.output = AttendeeOutputProcessor(websocket)
        self.policy_processor = InterviewPolicyProcessor(
            self.policy,
            register_speech_event=self.output.register_speech_event,
        )
        self.policy.speech_output = self.policy_processor.speak
        self.pipeline = Pipeline(
            [self.input, self.vad, self.stt, self.policy_processor, self.tts, self.output]
        )
        self.task = PipelineTask(
            self.pipeline,
            params=PipelineParams(
                audio_in_sample_rate=16000,
                audio_out_sample_rate=24000,
            ),
        )
        self.runner: PipelineRunner | None = None

    async def run(self) -> None:
        """Start the Pipecat pipeline and begin the greeting flow."""
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
        await self.task.cancel(reason="session_cleanup")
