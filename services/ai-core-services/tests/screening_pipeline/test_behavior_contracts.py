import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pipecat.frames.frames import (
    TTSSpeakFrame,
    VADUserStartedSpeakingFrame,
    VADUserStoppedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameDirection

from src.screening_pipeline.interview_policy import InterviewPolicy
from src.screening_pipeline.persistence import persist_qa_and_evaluation
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
    ANSWER_ACKNOWLEDGEMENT_TEXT,
    ANSWER_SETTLE_SECONDS,
    CLOSING_REPLY_TIMEOUT_SECONDS,
    CLOSING_TEXT,
    FILLER_TEXTS,
    GREETING_TEXT,
    MAX_FOLLOW_UPS_PER_QUESTION,
    MAX_SILENCE_PROMPTS,
    REPEAT_QUESTION_LIMIT_TEXT,
    REPEAT_QUESTION_PREFIX_TEXT,
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
    assert ANSWER_SETTLE_SECONDS == 2.0
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
async def test_complete_question_advances_without_waiting_for_core_api():
    """Phase 3: the Core API save must not block the next question."""
    save_transcript_may_finish = asyncio.Event()

    async def slow_save_transcript(qa_entry):
        await save_transcript_may_finish.wait()
        return True

    api_client = MagicMock()
    api_client.save_transcript = AsyncMock(side_effect=slow_save_transcript)
    api_client.save_evaluation = AsyncMock(return_value=True)

    policy = PipecatInterviewPolicy(
        "session-id",
        evaluator=MagicMock(),
        api_client=api_client,
        speech_output=AsyncMock(),
    )
    policy.is_active = True
    policy._ask_next_question = AsyncMock()
    policy.transcript_log = [
        {
            "interaction_type": "question",
            "candidate_answer": "",
            "follow_ups": [],
            "question_repeat_count": 0,
        }
    ]
    question_obj = {"id": 1, "question": "What is Docker?", "category": "must_have_matched"}
    eval_data = {"score": 8, "decision": "NEXT_QUESTION", "feedback": "Good"}

    await asyncio.wait_for(
        policy._complete_question(
            question_obj, "What is Docker?", "It runs containers", None, eval_data
        ),
        timeout=1,
    )

    # In-memory routing state and the next question both advanced already,
    # even though the Core API save is still stuck on save_transcript.
    assert len(policy.analysis_evaluations) == 1
    policy._ask_next_question.assert_awaited_once()
    api_client.save_evaluation.assert_not_awaited()

    save_transcript_may_finish.set()
    await policy._flush_pending_persist()
    api_client.save_evaluation.assert_awaited_once()


@pytest.mark.asyncio
async def test_finalize_awaits_pending_persist_before_closing_out():
    """Phase 3: finalize must not abandon an in-flight background save."""
    order = []

    async def slow_save_transcript(qa_entry):
        await asyncio.sleep(0.01)
        order.append("save_transcript")
        return True

    api_client = MagicMock()
    api_client.save_transcript = AsyncMock(side_effect=slow_save_transcript)
    api_client.save_evaluation = AsyncMock(return_value=True)
    api_client.update_status = AsyncMock(return_value=True)

    policy = PipecatInterviewPolicy(
        "session-id",
        evaluator=MagicMock(),
        llm_client=MagicMock(),
        api_client=api_client,
        speech_output=AsyncMock(),
    )
    policy.is_active = True
    policy._schedule_persist(
        persist_qa_and_evaluation(
            api_client, {"question_id": 1}, {"question_id": 1, "score": 8}
        )
    )

    async def fake_persist_interview_close(*args, **kwargs):
        order.append("persist_interview_close")

    with patch(
        "src.screening_pipeline.pipecat_policy.persist_interview_close",
        AsyncMock(side_effect=fake_persist_interview_close),
    ):
        await policy.finalize(reason="questions_completed")

    assert order == ["save_transcript", "persist_interview_close"]


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
    policy.transcript_log = [
        {
            "interaction_type": "question",
            "candidate_answer": "",
            "follow_ups": [],
            "question_repeat_count": 0,
        }
    ]
    question = {"question": "What is Docker?", "expected_keywords": []}

    await policy._handle_answer(
        question, "What is Docker?", "Please repeat.", {"decision": "REPEAT_QUESTION"}
    )
    policy._cancel_inactivity_deadline()
    await policy._handle_answer(
        question, "What is Docker?", "Repeat it again.", {"decision": "REPEAT_QUESTION"}
    )
    policy._cancel_inactivity_deadline()

    # First repeat: prefix and the question text are spoken as two separate
    # utterances (not concatenated into one string), so the question half
    # is spoken verbatim and hits the TTS cache.
    assert policy.speech_output.await_args_list[0].args[0] == REPEAT_QUESTION_PREFIX_TEXT
    assert policy.speech_output.await_args_list[1].args[0] == "What is Docker?"
    # Second repeat within the same question hits the one-repeat limit.
    third_response = policy.speech_output.await_args_list[2].args[0]
    assert third_response == REPEAT_QUESTION_LIMIT_TEXT
    assert "What is Docker?" not in third_response


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


def test_pipecat_runtime_waits_for_the_configured_turn_end_silence_before_finalizing_an_answer():
    runtime = PipecatInterviewRuntime(MagicMock(), "session-id")

    assert SCREENING_TURN_END_SILENCE_SECONDS == 1.5
    assert runtime.vad._vad_controller._vad_analyzer.params.stop_secs == 1.5


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


def test_pipecat_runtime_reuses_a_prewarmed_synthesizer_when_one_was_claimed():
    prewarmed = KokoroSynthesizer()
    prewarmed._cache["Hi!"] = [b"already-warm"]

    with patch(
        "src.screening_pipeline.pipecat_runtime.tts_prewarm_registry.claim",
        return_value=prewarmed,
    ) as claim:
        runtime = PipecatInterviewRuntime(MagicMock(), "session-id")

    claim.assert_called_once_with("session-id")
    assert runtime.tts.synthesizer is prewarmed
    assert runtime.tts.synthesizer._cache["Hi!"] == [b"already-warm"]


def test_pipecat_runtime_builds_a_fresh_synthesizer_when_nothing_was_prewarmed():
    with patch(
        "src.screening_pipeline.pipecat_runtime.tts_prewarm_registry.claim",
        return_value=None,
    ):
        runtime = PipecatInterviewRuntime(MagicMock(), "session-id")

    assert isinstance(runtime.tts.synthesizer, KokoroSynthesizer)
    assert runtime.tts.synthesizer._cache == {}


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
async def test_vad_stopped_speaking_notifies_the_policy():
    policy = MagicMock()
    processor = InterviewPolicyProcessor(policy)
    processor.push_frame = AsyncMock()

    await processor.process_frame(VADUserStoppedSpeakingFrame(), FrameDirection.DOWNSTREAM)

    policy.handle_candidate_speech_stopped.assert_called_once_with()


@pytest.mark.asyncio
async def test_pipecat_input_discards_audio_until_start_frame_arrives():
    processor = AttendeeInputProcessor()
    processor.push_frame = AsyncMock()

    await processor.push_audio(b"pcm", 24000)

    processor.push_frame.assert_not_awaited()


@pytest.mark.asyncio
async def test_start_warms_tts_cache_with_greeting_closing_and_all_questions():
    fake_session = MagicMock()
    fake_session.generated_questions = [
        {"id": "q1", "question": "What is a closure?"},
        {"id": "q2", "question": "Explain event loops."},
    ]
    warmer = AsyncMock()
    policy = PipecatInterviewPolicy(
        "session-id",
        evaluator=MagicMock(),
        api_client=MagicMock(),
        speech_output=AsyncMock(),
        tts_cache_warmer=warmer,
    )

    with patch(
        "src.screening_pipeline.pipecat_policy.interview_session_repo.get_by_id",
        AsyncMock(return_value=fake_session),
    ):
        await policy.start()
        await policy._tts_warm_task

    warmer.assert_awaited_once_with(
        [
            GREETING_TEXT,
            CLOSING_TEXT,
            SILENCE_PROMPT_TEXT,
            ANSWER_ACKNOWLEDGEMENT_TEXT,
            REPEAT_QUESTION_PREFIX_TEXT,
            REPEAT_QUESTION_LIMIT_TEXT,
            *FILLER_TEXTS,
            "What is a closure?",
            "Explain event loops.",
        ]
    )


@pytest.mark.asyncio
async def test_start_does_not_warm_tts_cache_when_no_warmer_configured():
    fake_session = MagicMock()
    fake_session.generated_questions = []
    policy = PipecatInterviewPolicy(
        "session-id",
        evaluator=MagicMock(),
        api_client=MagicMock(),
        speech_output=AsyncMock(),
    )

    with patch(
        "src.screening_pipeline.pipecat_policy.interview_session_repo.get_by_id",
        AsyncMock(return_value=fake_session),
    ):
        await policy.start()

    assert policy._tts_warm_task is None


@pytest.mark.asyncio
async def test_ending_interview_cancels_a_still_running_tts_warm_task():
    persistence = AsyncMock()
    api_client = MagicMock()
    api_client.update_status = AsyncMock(return_value=True)
    policy = PipecatInterviewPolicy(
        "session-id",
        evaluator=MagicMock(),
        llm_client=MagicMock(),
        api_client=api_client,
        speech_output=AsyncMock(),
    )

    async def never_finishes():
        await asyncio.sleep(3600)

    policy._tts_warm_task = asyncio.create_task(never_finishes())

    with patch(
        "src.screening_pipeline.pipecat_policy.persist_interview_close",
        persistence,
    ):
        await policy.end_interview("questions_completed")

    assert policy._tts_warm_task is None


@pytest.mark.asyncio
async def test_filler_schedule_speaks_nothing_if_cancelled_before_first_offset(monkeypatch):
    monkeypatch.setattr(
        "src.screening_pipeline.pipecat_policy.FILLER_SCHEDULE_SECONDS", [10.0]
    )
    speech_output = AsyncMock()
    policy = PipecatInterviewPolicy(
        "session-id", evaluator=MagicMock(), speech_output=speech_output
    )

    policy._start_filler_schedule()
    await asyncio.sleep(0.01)
    policy._cancel_filler_schedule()
    await asyncio.sleep(0.02)

    speech_output.assert_not_awaited()
    assert policy._filler_task is None


@pytest.mark.asyncio
async def test_filler_schedule_speaks_a_filler_once_its_offset_elapses(monkeypatch):
    monkeypatch.setattr(
        "src.screening_pipeline.pipecat_policy.FILLER_SCHEDULE_SECONDS", [0.01]
    )
    speech_output = AsyncMock()
    policy = PipecatInterviewPolicy(
        "session-id", evaluator=MagicMock(), speech_output=speech_output
    )

    policy._start_filler_schedule()
    await asyncio.sleep(0.05)

    assert speech_output.await_args_list[0].args[0] in FILLER_TEXTS
    # A filler must never flip the interaction state — barge-in detection
    # during "evaluating" depends on that state staying put (see
    # handle_candidate_activity).
    assert policy.current_interaction_state == "idle"

    policy._cancel_filler_schedule()


@pytest.mark.asyncio
async def test_filler_schedule_stops_after_its_last_offset(monkeypatch):
    monkeypatch.setattr(
        "src.screening_pipeline.pipecat_policy.FILLER_SCHEDULE_SECONDS", [0.01, 0.03]
    )
    speech_output = AsyncMock()
    policy = PipecatInterviewPolicy(
        "session-id", evaluator=MagicMock(), speech_output=speech_output
    )

    policy._start_filler_schedule()
    await asyncio.sleep(0.06)  # past both scheduled offsets

    assert speech_output.await_count == 2

    # A genuinely hung call must not get a third filler just because more
    # time passes — the schedule is exhausted, so it now waits silently.
    await asyncio.sleep(0.05)
    assert speech_output.await_count == 2

    policy._cancel_filler_schedule()


@pytest.mark.asyncio
async def test_filler_schedule_uses_absolute_offsets_not_relative_gaps(monkeypatch):
    """FILLER_SCHEDULE_SECONDS are absolute seconds since the candidate
    stopped talking, not gaps between fillers — so time actually spent
    speaking a filler must not push later ones back. Simulates a "slow"
    filler (speech_output takes real time, like real TTS playback would) and
    checks the second filler still lands close to its own absolute target
    instead of drifting by the first filler's playback time."""
    monkeypatch.setattr(
        "src.screening_pipeline.pipecat_policy.FILLER_SCHEDULE_SECONDS", [0.05, 0.25]
    )
    speech_output = AsyncMock()
    loop = asyncio.get_running_loop()
    call_times: list[float] = []

    async def slow_speech_output(text: str) -> None:
        call_times.append(loop.time())
        await asyncio.sleep(0.1)  # simulate real filler playback time

    speech_output.side_effect = slow_speech_output
    policy = PipecatInterviewPolicy(
        "session-id", evaluator=MagicMock(), speech_output=speech_output
    )

    started_at = loop.time()
    policy._start_filler_schedule()
    await asyncio.sleep(0.4)

    assert len(call_times) == 2
    assert (call_times[0] - started_at) < 0.15
    # Despite the first filler taking 0.1s to "speak", the second still
    # lands close to its absolute 0.25s target — not 0.05 + 0.1 + 0.25.
    assert (call_times[1] - started_at) < 0.35

    policy._cancel_filler_schedule()


@pytest.mark.asyncio
async def test_cancel_filler_schedule_stops_it_cleanly_mid_wait(monkeypatch):
    monkeypatch.setattr(
        "src.screening_pipeline.pipecat_policy.FILLER_SCHEDULE_SECONDS", [10.0]
    )
    policy = PipecatInterviewPolicy(
        "session-id", evaluator=MagicMock(), speech_output=AsyncMock()
    )

    policy._start_filler_schedule()
    task = policy._filler_task
    await asyncio.sleep(0)  # let it actually start sleeping
    policy._cancel_filler_schedule()

    assert policy._filler_task is None
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_filler_can_fire_during_the_settle_wait_itself(monkeypatch):
    """A filler is no longer held back until the settle wait ends — it fires
    at its own FILLER_SCHEDULE_SECONDS offset from VAD-stop even if that
    lands *during* settle. Safe because a candidate resuming speech mid-settle
    already gets the same InterruptionFrame barge-in as any other bot
    utterance (see handle_candidate_activity), regardless of
    current_interaction_state — there's no dead-air-vs-safety tradeoff in
    starting the clock this early."""
    monkeypatch.setattr("src.screening_pipeline.pipecat_policy.ANSWER_SETTLE_SECONDS", 0.2)
    monkeypatch.setattr(
        "src.screening_pipeline.pipecat_policy.FILLER_SCHEDULE_SECONDS", [0.05]
    )
    speech_output = AsyncMock()
    evaluator = MagicMock()

    async def never_resolves(**kwargs):
        await asyncio.sleep(3600)

    evaluator.classify_and_evaluate = never_resolves
    policy = PipecatInterviewPolicy(
        "session-id", evaluator=evaluator, speech_output=speech_output
    )
    policy.is_active = True
    policy.current_interaction_state = "listening"

    policy.handle_candidate_speech_stopped()
    policy.handle_candidate_speech("I need a moment")

    # Still well inside the 0.2s settle wait — the transcript hasn't even
    # been finalized into a classify_and_evaluate call yet.
    await asyncio.sleep(0.08)

    assert speech_output.await_args_list
    assert speech_output.await_args_list[0].args[0] in FILLER_TEXTS
    assert policy.current_interaction_state == "collecting_answer"

    # _process_after_answer_settles catches its own cancellation and returns
    # normally (see handle_candidate_activity's use of _cancel_answer_settle),
    # so this awaits cleanly rather than raising.
    task = policy._answer_settle_task
    policy._cancel_answer_settle()
    await task
    assert policy._filler_task is None


@pytest.mark.asyncio
async def test_fast_llm_response_after_settle_gets_no_filler(monkeypatch):
    """A fast enough LLM response — settle plus the call together still
    finishing before the first schedule offset elapses — must get no filler
    at all, not even one."""
    monkeypatch.setattr("src.screening_pipeline.pipecat_policy.ANSWER_SETTLE_SECONDS", 0.05)
    monkeypatch.setattr(
        "src.screening_pipeline.pipecat_policy.FILLER_SCHEDULE_SECONDS", [0.15]
    )
    speech_output = AsyncMock()
    evaluator = MagicMock()

    async def fast_classify(**kwargs):
        await asyncio.sleep(0.03)  # settle (0.05) + this (0.03) < offset (0.15)
        return {"intent": "SMALL_TALK", "response": "noted"}

    evaluator.classify_and_evaluate = fast_classify
    policy = PipecatInterviewPolicy(
        "session-id", evaluator=evaluator, speech_output=speech_output
    )
    policy.is_active = True
    policy.current_interaction_state = "listening"

    policy.handle_candidate_speech_stopped()
    policy.handle_candidate_speech("Okay")
    await policy._answer_settle_task

    # Exactly the real response — proves no filler was ever spoken first.
    speech_output.assert_awaited_once_with("noted")


@pytest.mark.asyncio
async def test_filler_schedule_is_cancelled_the_instant_classify_and_evaluate_resolves(monkeypatch):
    """Once classify_and_evaluate resolves, no further filler must ever fire
    — even though later FILLER_SCHEDULE_SECONDS offsets haven't elapsed yet,
    they must never overlap the real response that follows (see the
    try/finally around the classify_and_evaluate call in _process_speech)."""
    monkeypatch.setattr("src.screening_pipeline.pipecat_policy.ANSWER_SETTLE_SECONDS", 0.01)
    monkeypatch.setattr(
        "src.screening_pipeline.pipecat_policy.FILLER_SCHEDULE_SECONDS", [0.02, 0.05, 0.08]
    )
    speech_output = AsyncMock()
    evaluator = MagicMock()
    release = asyncio.Event()

    async def classify(**kwargs):
        await release.wait()
        return {"intent": "SMALL_TALK", "response": "noted"}

    evaluator.classify_and_evaluate = classify
    policy = PipecatInterviewPolicy(
        "session-id", evaluator=evaluator, speech_output=speech_output
    )
    policy.is_active = True
    policy.current_interaction_state = "listening"

    policy.handle_candidate_speech_stopped()
    policy.handle_candidate_speech("Okay")

    await asyncio.sleep(0.03)  # let the first offset (0.02) fire
    assert speech_output.await_args_list[0].args[0] in FILLER_TEXTS
    fillers_before_release = speech_output.await_count

    release.set()
    await policy._answer_settle_task

    # Only the real response was added after release — no fillers snuck in
    # past that point even though 0.05 / 0.08 were still ahead on the schedule.
    assert speech_output.await_count == fillers_before_release + 1
    assert speech_output.await_args_list[-1].args[0] == "noted"


@pytest.mark.asyncio
async def test_greeting_reply_cancels_the_filler_schedule_immediately(monkeypatch):
    """The greeting-reply shortcut in _process_speech never calls
    classify_and_evaluate, so it must disarm any armed filler schedule right
    away — otherwise a filler could still fire while _ask_next_question is
    speaking the real first question."""
    monkeypatch.setattr(
        "src.screening_pipeline.pipecat_policy.FILLER_SCHEDULE_SECONDS", [0.02]
    )
    speech_output = AsyncMock()
    policy = PipecatInterviewPolicy(
        "session-id", evaluator=MagicMock(), speech_output=speech_output
    )
    policy.transcript_log = [
        {"interaction_type": "greeting", "bot_speech": "hi", "candidate_answer": ""}
    ]
    policy._ask_next_question = AsyncMock()
    policy._start_filler_schedule()

    await policy._process_speech("hello")

    assert policy._filler_task is None
    await asyncio.sleep(0.05)  # past the schedule's only offset
    speech_output.assert_not_awaited()
    policy._ask_next_question.assert_awaited_once()


@pytest.mark.asyncio
async def test_closing_reply_cancels_the_filler_schedule_immediately(monkeypatch):
    """Same reasoning as the greeting-reply case, for the closing-reply
    shortcut."""
    monkeypatch.setattr(
        "src.screening_pipeline.pipecat_policy.FILLER_SCHEDULE_SECONDS", [0.02]
    )
    speech_output = AsyncMock()
    policy = PipecatInterviewPolicy(
        "session-id", evaluator=MagicMock(), speech_output=speech_output
    )
    policy.transcript_log = [
        {"interaction_type": "closing", "bot_speech": "bye", "candidate_answer": ""}
    ]
    policy._persist_closing_and_leave = AsyncMock()
    policy._start_filler_schedule()

    await policy._process_speech("okay bye")

    assert policy._filler_task is None
    await asyncio.sleep(0.05)
    speech_output.assert_not_awaited()
    policy._persist_closing_and_leave.assert_awaited_once()


def test_pick_random_filler_never_repeats_consecutively():
    policy = PipecatInterviewPolicy(
        "session-id", evaluator=MagicMock(), speech_output=AsyncMock()
    )

    picks = [policy._pick_random_filler() for _ in range(30)]

    assert all(pick in FILLER_TEXTS for pick in picks)
    assert all(a != b for a, b in zip(picks, picks[1:]))


@pytest.mark.asyncio
async def test_handle_candidate_activity_marks_candidate_as_speaking():
    policy = PipecatInterviewPolicy(
        "session-id", evaluator=MagicMock(), speech_output=AsyncMock()
    )
    policy.is_active = True

    policy.handle_candidate_activity()

    assert policy._candidate_speaking is True


@pytest.mark.asyncio
async def test_handle_candidate_speech_stopped_clears_the_speaking_flag():
    policy = PipecatInterviewPolicy(
        "session-id", evaluator=MagicMock(), speech_output=AsyncMock()
    )
    policy.is_active = True
    policy.handle_candidate_activity()

    policy.handle_candidate_speech_stopped()

    assert policy._candidate_speaking is False


@pytest.mark.asyncio
async def test_silence_prompt_is_withheld_while_a_long_answer_is_still_in_progress(
    monkeypatch,
):
    """Regression guard: an answer running past SILENCE_PROMPT_SECONDS with no
    pause must not be interrupted by "Are you there?" — only VAD confirming
    the candidate actually stopped may trigger it."""
    monkeypatch.setattr(
        "src.screening_pipeline.pipecat_policy.SILENCE_PROMPT_SECONDS", 0.03
    )
    monkeypatch.setattr(
        "src.screening_pipeline.pipecat_policy.CANDIDATE_SPEAKING_POLL_SECONDS", 0.02
    )
    speech_output = AsyncMock()
    policy = PipecatInterviewPolicy(
        "session-id", evaluator=MagicMock(), speech_output=speech_output
    )
    policy.is_active = True
    policy.transcript_log = []
    policy._begin_listening()
    policy.handle_candidate_activity()  # candidate starts a long, unbroken answer

    # Well past SILENCE_PROMPT_SECONDS, still mid-answer the whole time.
    await asyncio.sleep(0.15)

    assert speech_output.await_args_list == []
    assert policy.current_interaction_state == "listening"

    policy._cancel_inactivity_deadline()


@pytest.mark.asyncio
async def test_silence_prompt_fires_after_candidate_actually_stops(monkeypatch):
    monkeypatch.setattr(
        "src.screening_pipeline.pipecat_policy.SILENCE_PROMPT_SECONDS", 0.03
    )
    monkeypatch.setattr(
        "src.screening_pipeline.pipecat_policy.CANDIDATE_SPEAKING_POLL_SECONDS", 0.02
    )
    speech_output = AsyncMock()
    policy = PipecatInterviewPolicy(
        "session-id", evaluator=MagicMock(), speech_output=speech_output
    )
    policy.is_active = True
    policy.transcript_log = []
    policy._begin_listening()
    policy.handle_candidate_activity()
    await asyncio.sleep(0.1)  # mid-answer; withheld, as above
    assert speech_output.await_args_list == []

    policy.handle_candidate_speech_stopped()  # VAD confirms they finished
    await asyncio.sleep(0.1)  # a fresh SILENCE_PROMPT_SECONDS window elapses

    assert speech_output.await_args_list[0].args[0] == SILENCE_PROMPT_TEXT

    policy._cancel_inactivity_deadline()
