"""The bot opens with the company and role details HR wrote."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.screening_pipeline.pipecat_policy import PipecatInterviewPolicy
from src.screening_pipeline.prompts import (
    GREETING_CLOSING_TEXT,
    GREETING_TEXT,
    INTRO_TEXT_MAX_CHARS,
    build_greeting,
)
from src.screening_pipeline.tts_prewarm import known_bot_texts

INTRO = {
    "candidate_first_name": "Pooja",
    "company_name": "Josh Software",
    "company_details": "We build web and mobile products for clients worldwide",
    "job_title": "Senior Java Developer",
    "role_intro": "You'd join our payments team.",
}


def test_greeting_reads_the_company_and_role_details_as_written():
    assert build_greeting(**INTRO) == (
        "Hi Pooja! I am the AI interviewer from Josh Software. "
        "We build web and mobile products for clients worldwide. "
        "This screening is for the Senior Java Developer role. "
        "You'd join our payments team. " + GREETING_CLOSING_TEXT
    )


def test_missing_details_are_left_out():
    assert build_greeting(
        candidate_first_name="Pooja", company_name="Josh Software", job_title="QA Engineer"
    ) == (
        "Hi Pooja! I am the AI interviewer from Josh Software. "
        "This screening is for the QA Engineer role. " + GREETING_CLOSING_TEXT
    )


def test_no_details_at_all_is_the_standard_greeting():
    assert build_greeting() == GREETING_TEXT
    assert build_greeting(company_details="  ", role_intro="") == GREETING_TEXT


def test_long_or_messy_text_is_tidied_and_capped():
    messy = "We are   a team\nof builders"
    assert "We are a team of builders." in build_greeting(company_name="X", company_details=messy)

    long_text = ("We build software. " * 60).strip()
    greeting = build_greeting(company_name="X", company_details=long_text)
    spoken = greeting.split("I am the AI interviewer from X. ", 1)[1].split(" " + GREETING_CLOSING_TEXT)[0]
    assert len(spoken) <= INTRO_TEXT_MAX_CHARS
    assert spoken.endswith("software.")  # cut at a sentence end


def test_personalised_greeting_is_prepared_with_the_other_bot_audio():
    texts = known_bot_texts([{"question": "Q1?"}], ["Hi Pooja! ..."])
    assert "Hi Pooja! ..." in texts and GREETING_TEXT in texts and "Q1?" in texts
    assert known_bot_texts([], [None, ""]) == known_bot_texts([])


def _policy():
    api_client = MagicMock()
    api_client.update_status = AsyncMock(return_value=True)
    policy = PipecatInterviewPolicy(
        "sess-intro",
        evaluator=MagicMock(),
        llm_client=MagicMock(),
        api_client=api_client,
        speech_output=AsyncMock(),
    )
    policy._leave_bot_after_close = AsyncMock()
    return policy


async def _start(policy, intro):
    session = MagicMock(
        id=policy.session_id,
        status="in_progress",
        generated_questions=[],
        application_id="app-1",
        interview_metadata={},
    )
    repo = "src.screening_pipeline.pipecat_policy.interview_session_repo"
    with patch(f"{repo}.get_by_id", AsyncMock(return_value=session)), patch(
        f"{repo}.get_interview_intro", AsyncMock(return_value=intro)
    ):
        await policy.start()
    await policy.candidate_joined()


@pytest.mark.asyncio
async def test_bot_opens_with_the_company_and_role_intro():
    policy = _policy()
    await _start(policy, INTRO)

    spoken = [call.args[0] for call in policy.speech_output.await_args_list]
    assert spoken[:1] == [build_greeting(**INTRO)]
    assert policy.transcript_log[0]["bot_speech"] == build_greeting(**INTRO)
    await policy.end_interview("test")


@pytest.mark.asyncio
async def test_bot_uses_the_standard_greeting_when_details_cannot_be_read():
    policy = _policy()
    await _start(policy, None)

    spoken = [call.args[0] for call in policy.speech_output.await_args_list]
    assert spoken[:1] == [GREETING_TEXT]
    await policy.end_interview("test")


def test_the_personalised_greeting_is_prepared_before_everything_else():
    """It is said first and is the longest line, so it must be ready first."""
    texts = known_bot_texts([{"question": "Q1?"}], ["Hi Pooja! ..."])
    assert texts[0] == "Hi Pooja! ..."
    assert len(texts) == len(set(texts))


@pytest.mark.asyncio
async def test_greeting_audio_is_finished_before_it_is_spoken():
    """Aniket's screening: the long greeting was made while speaking, slower
    than playback, so it came out a sentence at a time with silences."""
    policy = _policy()
    order = []
    policy.speech_preparer = AsyncMock(side_effect=lambda text: order.append(("prepare", text)))
    policy.speech_output = AsyncMock(side_effect=lambda text: order.append(("speak", text)))
    await _start(policy, INTRO)

    greeting = build_greeting(**INTRO)
    assert order[:2] == [("prepare", greeting), ("speak", greeting)]
    await policy.end_interview("test")


@pytest.mark.asyncio
async def test_greeting_is_still_spoken_if_preparing_it_fails():
    policy = _policy()
    policy.speech_preparer = AsyncMock(side_effect=RuntimeError("tts down"))
    await _start(policy, INTRO)

    spoken = [call.args[0] for call in policy.speech_output.await_args_list]
    assert spoken[:1] == [build_greeting(**INTRO)]
    await policy.end_interview("test")


@pytest.mark.asyncio
async def test_first_question_follows_the_greeting_without_waiting_for_a_reply():
    """No "let me know when you're ready" and no 15-second wait: the bot asks
    the first question straight after the greeting."""
    policy = _policy()
    session = MagicMock(
        id=policy.session_id,
        status="in_progress",
        generated_questions=[{"id": 1, "category": "must_have_matched", "question": "What is Docker?"}],
        application_id="app-1",
        interview_metadata={},
    )
    repo = "src.screening_pipeline.pipecat_policy.interview_session_repo"
    with patch(f"{repo}.get_by_id", AsyncMock(return_value=session)), patch(
        f"{repo}.get_interview_intro", AsyncMock(return_value=INTRO)
    ):
        await policy.start()
    await policy.candidate_joined()

    spoken = [call.args[0] for call in policy.speech_output.await_args_list]
    assert spoken == [build_greeting(**INTRO), "What is Docker?"]
    assert "Let me know when you" not in spoken[0]
    assert policy.current_interaction_state == "listening"
    await policy.end_interview("test")
