import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pipecat.frames.frames import TTSSpeakFrame, VADUserStartedSpeakingFrame
from pipecat.processors.frame_processor import FrameDirection

from src.screening_pipeline.interview_policy import InterviewPolicy
from src.screening_pipeline.pipecat_policy import PipecatInterviewPolicy
from src.screening_pipeline.pipecat_stt import WhisperHttpSTTService
from src.screening_pipeline.pipecat_tts import KokoroSynthesizer, KokoroTTSService
from src.screening_pipeline.pipecat_runtime import (
    AttendeeInputProcessor,
    InterviewPolicyProcessor,
    PipecatInterviewRuntime,
    SCREENING_TURN_END_SILENCE_SECONDS,
)
from src.screening_pipeline.pipecat_transport import SpeechCompleteFrame
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


def test_interview_timing_and_prompt_contract_is_explicit():
    assert GREETING_TEXT == (
        "Hi! I am your interviewer for today's interview. Let's start with some technical questions."
    )
    assert CLOSING_TEXT == (
        "Thank you for your time today. Our HR team will be in touch shortly."
    )
    assert SILENCE_PROMPT_SECONDS == 30
    assert SILENCE_PROMPT_TEXT == "Are you there?"
    assert MAX_SILENCE_PROMPTS == 2
    assert ANSWER_SETTLE_SECONDS == 3
    assert CLOSING_REPLY_TIMEOUT_SECONDS == 30
    assert MAX_FOLLOW_UPS_PER_QUESTION == 1


def test_pipecat_policy_implements_shared_interview_policy():
    policy = PipecatInterviewPolicy(
        "session-id",
        evaluator=MagicMock(),
        speech_output=AsyncMock(),
    )

    assert isinstance(policy, InterviewPolicy)


@pytest.mark.asyncio
async def test_finalization_is_idempotent_for_disconnect_and_normal_close():
    persistence = AsyncMock()
    policy = PipecatInterviewPolicy(
        "session-id",
        evaluator=MagicMock(),
        llm_client=MagicMock(),
        api_client=MagicMock(),
        speech_output=AsyncMock(),
    )

    with patch(
        "src.screening_pipeline.pipecat_policy.persist_interview_close",
        persistence,
    ):
        await policy.finalize(reason="questions_completed")
        await policy.finalize(reason="transport_disconnected")

    persistence.assert_awaited_once_with(
        policy.api_client,
        policy.llm_client,
        policy.analysis_evaluations,
        policy.transcript_log,
        termination_reason="questions_completed",
    )
    assert policy.is_finalized is True


@pytest.mark.asyncio
async def test_policy_can_route_speech_to_an_injected_runtime_sink():
    speech_output = AsyncMock()
    policy = PipecatInterviewPolicy(
        "session-id",
        evaluator=MagicMock(),
        speech_output=speech_output,
    )
    policy.is_active = True

    await policy.speak("A policy response")

    speech_output.assert_awaited_once_with("A policy response")
    assert policy.current_interaction_state == "speaking"


@pytest.mark.asyncio
async def test_answer_segments_are_combined_before_evaluation(monkeypatch):
    speech_output = AsyncMock()
    policy = PipecatInterviewPolicy(
        "session-id",
        evaluator=MagicMock(),
        speech_output=speech_output,
    )
    policy.is_active = True
    policy.current_interaction_state = "listening"
    policy._process_speech = AsyncMock()
    monkeypatch.setattr("src.screening_pipeline.pipecat_policy.ANSWER_SETTLE_SECONDS", 0)

    policy.handle_candidate_speech("Docker packages")
    policy.handle_candidate_speech("applications and dependencies")
    await policy._answer_settle_task

    policy._process_speech.assert_awaited_once_with(
        "Docker packages applications and dependencies"
    )


@pytest.mark.asyncio
async def test_inactivity_finalizes_and_requests_bot_leave(monkeypatch):
    api_client = MagicMock()
    api_client.update_status = AsyncMock(return_value=True)
    policy = PipecatInterviewPolicy(
        "session-id",
        evaluator=MagicMock(),
        llm_client=MagicMock(),
        api_client=api_client,
        speech_output=AsyncMock(),
    )
    policy.is_active = True
    policy.current_interaction_state = "listening"
    now = asyncio.get_running_loop().time()
    policy._last_candidate_activity_at = now
    policy._inactivity_cycle_started_at = now
    policy._leave_bot_after_close = AsyncMock()
    monkeypatch.setattr("src.screening_pipeline.pipecat_policy.SILENCE_PROMPT_SECONDS", 0)

    with patch("src.screening_pipeline.pipecat_policy.persist_interview_close", AsyncMock()) as persistence:
        await policy._end_after_inactivity()

    assert policy.termination_reason == "candidate_silence"
    persistence.assert_awaited_once()
    api_client.update_status.assert_awaited_once_with("completed")
    policy._leave_bot_after_close.assert_awaited_once()
    assert [call.args[0] for call in policy.speech_output.await_args_list] == [
        SILENCE_PROMPT_TEXT,
        SILENCE_PROMPT_TEXT,
        CLOSING_TEXT,
    ]


@pytest.mark.asyncio
async def test_question_is_repeated_at_most_once():
    policy = PipecatInterviewPolicy(
        "session-id",
        evaluator=MagicMock(),
        speech_output=AsyncMock(),
    )
    policy.is_active = True
    policy.evaluator.evaluate_answer = AsyncMock(
        return_value={"decision": "REPEAT_QUESTION"}
    )
    policy.transcript_log = [
        {
            "interaction_type": "question",
            "candidate_answer": "",
            "follow_ups": [],
            "question_repeat_count": 0,
        }
    ]
    question = {"question": "What is Docker?", "expected_keywords": []}

    await policy._handle_answer(question, "What is Docker?", "Please repeat.")
    policy._cancel_inactivity_deadline()
    await policy._handle_answer(question, "What is Docker?", "Repeat it again.")
    policy._cancel_inactivity_deadline()

    first_response = policy.speech_output.await_args_list[0].args[0]
    second_response = policy.speech_output.await_args_list[1].args[0]
    assert first_response == "Let me repeat the question: What is Docker?"
    assert "already repeated" in second_response
    assert "What is Docker?" not in second_response


@pytest.mark.asyncio
async def test_kokoro_requires_external_artifacts_by_default(monkeypatch, tmp_path):
    synthesizer = KokoroSynthesizer(
        model_path=str(tmp_path / "missing.onnx"),
        voices_path=str(tmp_path / "missing.bin"),
    )

    with pytest.raises(FileNotFoundError, match="Kokoro artifacts are missing"):
        await synthesizer.ensure_ready()


def test_kokoro_defaults_to_the_external_model_root(monkeypatch):
    monkeypatch.setattr(
        "src.screening_pipeline.pipecat_tts.settings.ai_models_host_dir",
        "/external/models",
    )
    monkeypatch.setattr("src.screening_pipeline.pipecat_tts.settings.kokoro_model_path", None)
    monkeypatch.setattr("src.screening_pipeline.pipecat_tts.settings.kokoro_voices_path", None)

    synthesizer = KokoroSynthesizer()

    assert synthesizer.model_path == "/external/models/kokoro/kokoro-v1.0.onnx"
    assert synthesizer.voices_path == "/external/models/kokoro/voices-v1.0.bin"


def test_pipecat_whisper_adapter_uses_segmented_stt():
    assert WhisperHttpSTTService(sample_rate=16000).wants_wav_segments is True


def test_pipecat_runtime_waits_two_seconds_before_finalizing_an_answer():
    runtime = PipecatInterviewRuntime(MagicMock(), "session-id")

    assert SCREENING_TURN_END_SILENCE_SECONDS == 2.0
    assert runtime.vad._vad_controller._vad_analyzer.params.stop_secs == 2.0


@pytest.mark.asyncio
async def test_pipecat_kokoro_adapter_preserves_pcm_audio_metadata():
    class FakeKokoroSynthesizer:
        async def ensure_ready(self):
            pass

        async def synthesize(self, _text):
            yield b"first-frame"
            yield b"second-frame"

    service = KokoroTTSService(synthesizer=FakeKokoroSynthesizer())

    frames = [frame async for frame in service.run_tts("Hello", "context-1")]

    assert [frame.audio for frame in frames] == [b"first-frame", b"second-frame"]
    assert [(frame.sample_rate, frame.num_channels) for frame in frames] == [
        (24000, 1),
        (24000, 1),
    ]


@pytest.mark.asyncio
async def test_pipecat_kokoro_adapter_validates_before_pipeline_start():
    synthesizer = MagicMock()
    synthesizer.ensure_ready = AsyncMock()
    service = KokoroTTSService(synthesizer=synthesizer)

    await service.validate_ready()

    synthesizer.ensure_ready.assert_awaited_once()


def test_pipecat_runtime_builds_without_starting_a_live_session():
    runtime = PipecatInterviewRuntime(MagicMock(), "session-id")

    assert runtime.runner is None
    assert runtime.task.params.audio_in_sample_rate == 16000
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
async def test_candidate_speech_interrupts_bot_audio_so_the_answer_is_preserved():
    policy = MagicMock()
    processor = InterviewPolicyProcessor(policy)
    sent_frames = []

    async def push_frame(frame, _direction):
        sent_frames.append(frame)

    processor.push_frame = push_frame

    await processor.process_frame(VADUserStartedSpeakingFrame(), FrameDirection.DOWNSTREAM)

    policy.handle_candidate_activity.assert_called_once_with()
    assert any(frame.__class__.__name__ == "InterruptionFrame" for frame in sent_frames)


@pytest.mark.asyncio
async def test_pipecat_input_discards_audio_until_start_frame_arrives():
    processor = AttendeeInputProcessor()
    processor.push_frame = AsyncMock()

    await processor.push_audio(b"pcm", 24000)

    processor.push_frame.assert_not_awaited()
