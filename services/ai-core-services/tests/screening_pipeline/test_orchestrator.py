import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.screening_pipeline.orchestrator import InterviewOrchestrator


class FakeTTSClient:
    def __init__(self):
        self.spoken = []

    async def synthesize(self, text):
        self.spoken.append(text)
        if False:
            yield b""


class FakeEvaluator:
    def __init__(self, response):
        self.response = response

    async def evaluate_answer(self, **_kwargs):
        return self.response


@pytest.mark.asyncio
async def test_close_interview_saves_closing_reply_then_requests_bot_leave(monkeypatch):
    events = []

    class RecordingTTSClient:
        async def synthesize(self, text):
            events.append(("spoken", text))
            if False:
                yield b""

    async def record_persistence(*_args, **kwargs):
        events.append(("saved", None))

    async def record_leave(bot_id):
        events.append(("leave_requested", bot_id))
        return SimpleNamespace(status="leaving", error_message=None)

    orch = InterviewOrchestrator(
        "session-id",
        MagicMock(),
        stt_client=MagicMock(),
        tts_client=RecordingTTSClient(),
        evaluator=MagicMock(),
        api_client=MagicMock(),
    )
    orch.is_active = True
    orch.session = SimpleNamespace(interview_metadata={"bot_id": "bot-123"})

    monkeypatch.setattr(
        "src.screening_pipeline.orchestrator.persist_interview_close", record_persistence
    )
    monkeypatch.setattr("src.screening_pipeline.orchestrator.bot_client.leave_bot", record_leave)

    await orch._close_interview()

    assert events == [
        ("spoken", "Thank you for your time today. Our HR team will be in touch shortly."),
    ]
    assert orch.current_interaction_state == "closing"
    assert orch._silence_prompt_task is None

    # "Thank you." is normally filtered as noise during a technical answer,
    # but is the expected response to the final closing greeting.
    orch.handle_candidate_speech("Thank you.")
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    assert events == [
        ("spoken", "Thank you for your time today. Our HR team will be in touch shortly."),
        ("saved", None),
        ("leave_requested", "bot-123"),
    ]
    assert orch.transcript_log[-1]["candidate_answer"] == "Thank you."
    assert orch.is_active is False


@pytest.mark.asyncio
async def test_close_interview_without_reply_saves_then_leaves_after_silent_timeout(monkeypatch):
    events = []

    class RecordingTTSClient:
        async def synthesize(self, text):
            events.append(("spoken", text))
            if False:
                yield b""

    async def record_persistence(*_args, **kwargs):
        events.append(("saved", None))

    async def record_leave(bot_id):
        events.append(("leave_requested", bot_id))
        return SimpleNamespace(status="leaving", error_message=None)

    orch = InterviewOrchestrator(
        "session-id",
        MagicMock(),
        stt_client=MagicMock(),
        tts_client=RecordingTTSClient(),
        evaluator=MagicMock(),
        api_client=MagicMock(),
    )
    orch.is_active = True
    orch.session = SimpleNamespace(interview_metadata={"bot_id": "bot-123"})

    monkeypatch.setattr(
        "src.screening_pipeline.orchestrator.persist_interview_close", record_persistence
    )
    monkeypatch.setattr("src.screening_pipeline.orchestrator.bot_client.leave_bot", record_leave)
    monkeypatch.setattr(
        "src.screening_pipeline.orchestrator.CLOSING_REPLY_TIMEOUT_SECONDS", 0
    )

    await orch._close_interview()
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    assert events == [
        ("spoken", "Thank you for your time today. Our HR team will be in touch shortly."),
        ("saved", None),
        ("leave_requested", "bot-123"),
    ]
    assert orch.transcript_log[-1]["candidate_answer"] == ""
    assert orch._silence_prompt_task is None
    assert orch.is_active is False


@pytest.mark.asyncio
async def test_orchestrator_start_aborts_without_session():
    ws = MagicMock()
    orch = InterviewOrchestrator(
        "missing-session",
        ws,
        stt_client=MagicMock(),
        tts_client=MagicMock(),
        evaluator=MagicMock(),
        llm_client=MagicMock(),
        api_client=MagicMock(),
    )

    with patch(
        "src.screening_pipeline.orchestrator.interview_session_repo.get_by_id",
        new_callable=AsyncMock,
        return_value=None,
    ):
        await orch.start()

    assert orch.is_active is False


@pytest.mark.asyncio
async def test_silence_prompt_is_spoken_after_listening_timeout(monkeypatch):
    tts_client = FakeTTSClient()
    orch = InterviewOrchestrator(
        "session-id",
        MagicMock(),
        stt_client=MagicMock(),
        tts_client=tts_client,
        evaluator=MagicMock(),
    )
    orch.is_active = True
    orch.transcript_log = [{"interaction_type": "question"}]
    monkeypatch.setattr("src.screening_pipeline.orchestrator.SILENCE_PROMPT_SECONDS", 0)

    orch._begin_listening()
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    assert tts_client.spoken == ["Are you there?"]
    assert orch.transcript_log[-1]["silence_prompts"] == [
        {"bot_speech": "Are you there?", "candidate_reply": ""}
    ]


@pytest.mark.asyncio
async def test_continuous_silence_prompts_three_times_then_starts_closing(monkeypatch):
    tts_client = FakeTTSClient()
    orch = InterviewOrchestrator(
        "session-id",
        MagicMock(),
        stt_client=MagicMock(),
        tts_client=tts_client,
        evaluator=MagicMock(),
    )
    closed = []

    async def record_close():
        closed.append(True)

    orch.is_active = True
    orch.transcript_log = [{"interaction_type": "question"}]
    monkeypatch.setattr("src.screening_pipeline.orchestrator.SILENCE_PROMPT_SECONDS", 0)
    monkeypatch.setattr(orch, "_close_interview", record_close)

    orch._begin_listening()
    for _ in range(12):
        await asyncio.sleep(0)

    assert tts_client.spoken == ["Are you there?"] * 3
    assert len(orch.transcript_log[-1]["silence_prompts"]) == 3
    assert closed == [True]
    assert orch._silence_prompt_task is None


@pytest.mark.asyncio
async def test_candidate_activity_cancels_remaining_continuous_silence_prompts(monkeypatch):
    tts_client = FakeTTSClient()
    orch = InterviewOrchestrator(
        "session-id",
        MagicMock(),
        stt_client=MagicMock(),
        tts_client=tts_client,
        evaluator=MagicMock(),
    )
    orch.is_active = True
    orch.transcript_log = [{"interaction_type": "question"}]
    monkeypatch.setattr("src.screening_pipeline.orchestrator.SILENCE_PROMPT_SECONDS", 0.01)

    orch._begin_listening()
    orch.handle_candidate_activity()
    await asyncio.sleep(0.02)

    assert tts_client.spoken == []
    assert orch._silence_prompt_task is None


@pytest.mark.asyncio
async def test_delayed_silence_cycle_restarts_instead_of_accumulating_to_close(monkeypatch):
    tts_client = FakeTTSClient()
    orch = InterviewOrchestrator(
        "session-id",
        MagicMock(),
        stt_client=MagicMock(),
        tts_client=tts_client,
        evaluator=MagicMock(),
    )
    closed = []

    async def record_close():
        closed.append(True)

    orch.is_active = True
    orch.current_interaction_state = "listening"
    orch.transcript_log = [{"interaction_type": "question"}]
    orch._silence_prompt_count = 2
    orch._silence_cycle_started_at = asyncio.get_running_loop().time() - 1
    monkeypatch.setattr("src.screening_pipeline.orchestrator.SILENCE_PROMPT_SECONDS", 0)
    monkeypatch.setattr(
        "src.screening_pipeline.orchestrator.SILENCE_PROMPT_CYCLE_GRACE_SECONDS", 0
    )
    monkeypatch.setattr(orch, "_close_interview", record_close)

    await orch._prompt_after_silence()

    assert orch._silence_prompt_count == 1
    assert closed == []
    orch._cancel_silence_prompt()


def test_silence_prompt_reply_is_saved_in_transcript():
    orch = InterviewOrchestrator(
        "session-id",
        MagicMock(),
        stt_client=MagicMock(),
        tts_client=FakeTTSClient(),
        evaluator=MagicMock(),
    )
    orch.transcript_log = [
        {
            "interaction_type": "question",
            "silence_prompts": [
                {"bot_speech": "Are you there?", "candidate_reply": ""}
            ],
        }
    ]
    orch._awaiting_silence_reply = True

    orch._record_silence_reply("Yes, I am here.")

    assert orch.transcript_log[-1]["silence_prompts"][-1]["candidate_reply"] == "Yes, I am here."


@pytest.mark.asyncio
async def test_conversational_reply_does_not_start_silence_prompt():
    tts_client = FakeTTSClient()
    orch = InterviewOrchestrator(
        "session-id",
        MagicMock(),
        stt_client=MagicMock(),
        tts_client=tts_client,
        evaluator=MagicMock(),
    )
    orch.is_active = True
    orch.transcript_log = [{"interaction_type": "question"}]

    await orch._handle_conversational("Could you repeat that?", "Certainly.")

    assert tts_client.spoken == ["Certainly."]
    assert orch.current_interaction_state == "listening"
    assert orch._silence_prompt_task is None


@pytest.mark.asyncio
async def test_candidate_activity_cancels_pending_silence_prompt():
    orch = InterviewOrchestrator(
        "session-id",
        MagicMock(),
        stt_client=MagicMock(),
        tts_client=FakeTTSClient(),
        evaluator=MagicMock(),
    )
    orch.is_active = True
    orch._begin_listening()

    task = orch._silence_prompt_task
    orch.handle_candidate_activity()
    await asyncio.sleep(0)

    assert task.cancelled()
    assert orch._silence_prompt_task is None


@pytest.mark.asyncio
async def test_repeat_main_question_is_conversational_and_next_answer_stays_main_answer():
    tts_client = FakeTTSClient()
    orch = InterviewOrchestrator(
        "session-id",
        MagicMock(),
        stt_client=MagicMock(),
        tts_client=tts_client,
        evaluator=FakeEvaluator({"decision": "REPEAT_QUESTION"}),
        api_client=MagicMock(),
    )
    orch.is_active = True
    orch.transcript_log = [
        {
            "interaction_type": "question",
            "bot_speech": "What is Docker?",
            "candidate_answer": "",
            "follow_ups": [],
        }
    ]

    await orch._handle_answer({"expected_keywords": []}, "What is Docker?", "Please repeat.")

    assert orch.transcript_log[-1]["candidate_answer"] == "Please repeat."
    assert orch.transcript_log[-1]["conversational_turns"] == [
        {
            "candidate_speech": "Please repeat.",
            "ai_response": "Let me repeat the question: What is Docker?",
        }
    ]
    assert tts_client.spoken[-1] == "Let me repeat the question: What is Docker?"
    assert "primary_eval" not in orch.transcript_log[-1]
    assert orch.transcript_log[-1]["follow_ups"] == []


@pytest.mark.asyncio
async def test_repeat_follow_up_repeats_the_same_follow_up_without_creating_another():
    tts_client = FakeTTSClient()
    orch = InterviewOrchestrator(
        "session-id",
        MagicMock(),
        stt_client=MagicMock(),
        tts_client=tts_client,
        evaluator=FakeEvaluator({"decision": "REPEAT_QUESTION"}),
        api_client=MagicMock(),
    )
    orch.is_active = True
    orch.transcript_log = [
        {
            "interaction_type": "question",
            "bot_speech": "What is Docker?",
            "candidate_answer": "A container platform.",
            "primary_eval": {"keywords_missing": ["image"]},
            "follow_ups": [
                {"ai_response": "What is a Docker image?", "candidate_speech": ""}
            ],
        }
    ]

    await orch._handle_answer({"expected_keywords": []}, "What is Docker?", "Please repeat.")

    assert len(orch.transcript_log[-1]["follow_ups"]) == 1
    assert orch.transcript_log[-1]["follow_ups"][0]["candidate_speech"] == ""
    assert tts_client.spoken[-1] == "Let me repeat the question: What is a Docker image?"
