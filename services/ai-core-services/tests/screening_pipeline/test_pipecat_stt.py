from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.screening_pipeline.pipecat_policy import PipecatInterviewPolicy
from src.screening_pipeline.pipecat_stt import WhisperHttpSTTService, _echoes_prompt

QUESTION = {
    "question": "Can you explain the difference between a HashMap and a ConcurrentHashMap?",
    "skill_focus": "Core Java",
    "expected_keywords": ["thread-safety", "CAS"],
}


def _policy():
    return PipecatInterviewPolicy(
        "session-id", evaluator=MagicMock(), api_client=MagicMock(), speech_output=AsyncMock()
    )


def test_stt_prompt_carries_the_question_and_its_key_terms():
    policy = _policy()
    assert policy.stt_prompt() is None  # greeting: no question yet

    policy.current_question_obj = QUESTION

    assert policy.stt_prompt() == (
        "Can you explain the difference between a HashMap and a ConcurrentHashMap? "
        "Key terms: Core Java, thread-safety, CAS."
    )


def test_echoed_prompt_is_detected_but_real_answers_are_not():
    prompt = "Can you explain the difference between a HashMap and a ConcurrentHashMap?"
    assert _echoes_prompt("the difference between a HashMap and a ConcurrentHashMap", prompt)
    assert not _echoes_prompt("A HashMap allows one null key", prompt)
    assert not _echoes_prompt("HashMap", prompt)  # too short to judge


def _whisper_response(text):
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {"text": text}
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.post = AsyncMock(return_value=response)
    return client


@pytest.mark.asyncio
async def test_whisper_request_includes_the_prompt_and_drops_echoes():
    service = WhisperHttpSTTService(
        sample_rate=16000, prompt_provider=lambda: QUESTION["question"]
    )
    audio = bytes(16000 * 2)

    client = _whisper_response("A ConcurrentHashMap is thread safe.")
    with patch("src.screening_pipeline.pipecat_stt.httpx.AsyncClient", return_value=client):
        frames = [frame async for frame in service.run_stt(audio)]
    assert client.post.await_args.kwargs["data"]["prompt"] == QUESTION["question"]
    assert frames[0].text == "A ConcurrentHashMap is thread safe."

    echo = _whisper_response("explain the difference between a HashMap and a ConcurrentHashMap")
    with patch("src.screening_pipeline.pipecat_stt.httpx.AsyncClient", return_value=echo):
        assert [frame async for frame in service.run_stt(audio)] == []
