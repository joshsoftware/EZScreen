import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pipecat.frames.frames import TTSSpeakFrame

from src.screening_pipeline.orchestrator import InterviewOrchestrator
from src.screening_pipeline.interview_policy import InterviewPolicy
from src.screening_pipeline.tts_client import LocalKokoroTTSClient
from src.screening_pipeline.pipecat_stt import WhisperHttpSTTService
from src.screening_pipeline.pipecat_tts import KokoroTTSService
from src.screening_pipeline.pipecat_runtime import (
    AttendeeInputProcessor,
    InterviewPolicyProcessor,
    PipecatInterviewRuntime,
)
from src.screening_pipeline.pipecat_transport import SpeechCompleteFrame
from src.screening_pipeline.prompts import (
    CLOSING_REPLY_TIMEOUT_SECONDS,
    CLOSING_TEXT,
    GREETING_TEXT,
    MAX_FOLLOW_UPS_PER_QUESTION,
    MAX_SILENCE_PROMPTS,
    SILENCE_PROMPT_SECONDS,
    SILENCE_PROMPT_TEXT,
)


def test_interview_timing_and_prompt_contract_is_explicit():
    assert GREETING_TEXT == (
        "Hi! I am your interviewer for today's interview. Let's start with some technical questions."
    )
    assert CLOSING_TEXT == (
        "Thank you for your time today. Our HR team will be in touch shortly."
    )
    assert SILENCE_PROMPT_TEXT == "Are you there?"
    assert SILENCE_PROMPT_SECONDS == 30
    assert MAX_SILENCE_PROMPTS == 3
    assert CLOSING_REPLY_TIMEOUT_SECONDS == 30
    assert MAX_FOLLOW_UPS_PER_QUESTION == 1


def test_legacy_orchestrator_implements_shared_interview_policy():
    orchestrator = InterviewOrchestrator(
        "session-id",
        MagicMock(),
        stt_client=MagicMock(),
        tts_client=MagicMock(),
        evaluator=MagicMock(),
    )

    assert isinstance(orchestrator, InterviewPolicy)


@pytest.mark.asyncio
async def test_finalization_is_idempotent_for_disconnect_and_normal_close():
    persistence = AsyncMock()
    orchestrator = InterviewOrchestrator(
        "session-id",
        MagicMock(),
        stt_client=MagicMock(),
        tts_client=MagicMock(),
        evaluator=MagicMock(),
        llm_client=MagicMock(),
        api_client=MagicMock(),
    )

    with patch(
        "src.screening_pipeline.orchestrator.persist_interview_close",
        persistence,
    ):
        await orchestrator.finalize(reason="questions_completed")
        await orchestrator.finalize(reason="session_ended")

    persistence.assert_awaited_once_with(
        orchestrator.api_client,
        orchestrator.llm_client,
        orchestrator.analysis_evaluations,
        orchestrator.transcript_log,
        termination_reason="questions_completed",
    )
    assert orchestrator.is_finalized is True


@pytest.mark.asyncio
async def test_policy_can_route_speech_to_an_injected_runtime_sink():
    speech_output = AsyncMock()
    orchestrator = InterviewOrchestrator(
        "session-id",
        MagicMock(),
        stt_client=MagicMock(),
        tts_client=MagicMock(),
        evaluator=MagicMock(),
        speech_output=speech_output,
    )
    orchestrator.is_active = True

    await orchestrator.speak("A policy response")

    speech_output.assert_awaited_once_with("A policy response")
    assert orchestrator.current_interaction_state == "speaking"


@pytest.mark.asyncio
async def test_kokoro_requires_external_artifacts_by_default(monkeypatch, tmp_path):
    monkeypatch.setattr("src.screening_pipeline.tts_client.settings.kokoro_allow_download", False)
    client = LocalKokoroTTSClient(
        model_path=str(tmp_path / "missing.onnx"),
        voices_path=str(tmp_path / "missing.bin"),
    )

    with pytest.raises(FileNotFoundError, match="externally provisioned files"):
        await client._ensure_models()


def test_kokoro_defaults_to_the_external_model_root(monkeypatch):
    monkeypatch.setattr(
        "src.screening_pipeline.tts_client.settings.ai_models_host_dir",
        "/external/models",
    )
    monkeypatch.setattr("src.screening_pipeline.tts_client.settings.kokoro_model_path", None)
    monkeypatch.setattr("src.screening_pipeline.tts_client.settings.kokoro_voices_path", None)

    client = LocalKokoroTTSClient()

    assert client.model_path == "/external/models/kokoro/kokoro-v1.0.onnx"
    assert client.voices_path == "/external/models/kokoro/voices-v1.0.bin"


def test_pipecat_whisper_adapter_builds_the_existing_wav_contract():
    audio = b"\x01\x02" * 12000

    wav_bytes = WhisperHttpSTTService._wav_bytes(audio, 24000)

    assert wav_bytes.startswith(b"RIFF")
    assert b"WAVE" in wav_bytes[:12]


@pytest.mark.asyncio
async def test_pipecat_kokoro_adapter_preserves_pcm_audio_metadata():
    class FakeKokoroClient:
        async def synthesize(self, _text):
            yield b"first-frame"
            yield b"second-frame"

    service = KokoroTTSService(client=FakeKokoroClient())

    frames = [frame async for frame in service.run_tts("Hello", "context-1")]

    assert [frame.audio for frame in frames] == [b"first-frame", b"second-frame"]
    assert [(frame.sample_rate, frame.num_channels) for frame in frames] == [
        (24000, 1),
        (24000, 1),
    ]


@pytest.mark.asyncio
async def test_pipecat_kokoro_adapter_validates_before_pipeline_start():
    client = MagicMock()
    client._ensure_models = AsyncMock()
    service = KokoroTTSService(client=client)

    await service.validate_ready()

    client._ensure_models.assert_awaited_once()


def test_pipecat_runtime_builds_without_starting_a_live_session():
    runtime = PipecatInterviewRuntime(MagicMock(), "session-id")

    assert runtime.runner is None
    assert runtime.task.params.audio_in_sample_rate == 24000
    assert runtime.task.params.audio_out_sample_rate == 24000
    assert runtime.input.ready.is_set() is False


@pytest.mark.asyncio
async def test_pipecat_policy_processor_sends_policy_speech_downstream():
    registered_events = []
    processor = InterviewPolicyProcessor(
        MagicMock(),
        register_speech_event=registered_events.append,
    )
    sent_frames = []

    async def push_frame(frame, _direction):
        sent_frames.append(frame)
        if isinstance(frame, SpeechCompleteFrame):
            frame.event.set()

    processor.push_frame = push_frame

    await processor.speak("A policy response")

    assert len(sent_frames) == 2
    assert isinstance(sent_frames[0], TTSSpeakFrame)
    assert sent_frames[0].text == "A policy response"
    assert isinstance(sent_frames[1], SpeechCompleteFrame)
    assert registered_events == [sent_frames[1].event]


@pytest.mark.asyncio
async def test_pipecat_input_discards_audio_until_start_frame_arrives():
    processor = AttendeeInputProcessor()
    processor.push_frame = AsyncMock()

    await processor.push_audio(b"pcm", 24000)

    processor.push_frame.assert_not_awaited()
