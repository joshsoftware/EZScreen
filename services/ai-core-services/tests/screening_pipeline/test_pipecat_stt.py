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


def test_low_confidence_segments_are_dropped():
    from src.screening_pipeline.pipecat_stt import _confident_text

    body = {
        "text": "A HashMap is not thread safe. See you on the next slide.",
        "segments": [
            {"text": " A HashMap is not thread safe.", "no_speech_prob": 0.01, "avg_logprob": -0.25, "compression_ratio": 1.1},
            {"text": " See you on the next slide.", "no_speech_prob": 0.85, "avg_logprob": -0.8, "compression_ratio": 1.0},
            {"text": " slide slide slide slide", "no_speech_prob": 0.1, "avg_logprob": -0.3, "compression_ratio": 3.1},
            {"text": " mumble", "no_speech_prob": 0.2, "avg_logprob": -1.4, "compression_ratio": 1.0},
        ],
    }

    assert _confident_text(body) == "A HashMap is not thread safe."
    assert _confident_text({"text": " plain json "}) == "plain json"


def test_long_hard_to_transcribe_answer_is_kept():
    """A real 17-second answer on a noisy mic came back below the log-prob
    bar and was dropped whole; the bot then asked "Are you there?"."""
    from src.screening_pipeline.pipecat_stt import _confident_text

    answer = " I'll choose a ConcurrentHashMap when I want the maps to be synchronized."
    body = {
        "text": answer,
        "segments": [
            {"text": answer, "no_speech_prob": 0.04, "avg_logprob": -1.1, "compression_ratio": 1.5},
        ],
    }

    assert _confident_text(body) == answer.strip()


@pytest.mark.asyncio
async def test_whisper_timeout_is_retried_once():
    import httpx

    service = WhisperHttpSTTService(sample_rate=16000)
    ok = _whisper_response("A ConcurrentHashMap is thread safe.")
    failing = MagicMock()
    failing.__aenter__ = AsyncMock(return_value=failing)
    failing.__aexit__ = AsyncMock(return_value=False)
    failing.post = AsyncMock(side_effect=httpx.ReadTimeout(""))
    with patch(
        "src.screening_pipeline.pipecat_stt.httpx.AsyncClient", side_effect=[failing, ok]
    ):
        frames = [frame async for frame in service.run_stt(bytes(16000 * 2))]

    assert [f.text for f in frames] == ["A ConcurrentHashMap is thread safe."]
