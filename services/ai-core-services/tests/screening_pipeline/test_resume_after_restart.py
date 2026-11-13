"""Resume an interview after the service restarted mid-way.

On staging the service went down during an interview; the bot stayed in the
meeting, Attendee reconnected it, and the new runtime greeted the candidate
and asked question 1 again. The re-asked questions were saved as skips over
the real scores, and the summary and transcript held only what came after
the restart.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.screening_pipeline.finished_interviews import _finished_bots
from src.screening_pipeline.pipecat_policy import PipecatInterviewPolicy
from src.screening_pipeline.prompts import GREETING_TEXT, RESUME_TEXT

QUESTIONS = [
    {"id": 1, "question": "Explain sagas.", "category": "must_have_matched"},
    {"id": 2, "question": "Explain circuit breakers.", "category": "must_have_matched"},
    {"id": 3, "question": "Explain Kafka ordering.", "category": "must_have_matched"},
]

Q1_EVALUATION = {"question_id": 1, "category": "must_have_matched", "score": 7.0}


@pytest.fixture(autouse=True)
def _clean_registries():
    _finished_bots.clear()
    yield
    _finished_bots.clear()


def _session(conversation_transcript=None):
    metadata = {"bot_id": "bot-1"}
    if conversation_transcript is not None:
        metadata["conversation_transcript"] = conversation_transcript
    return MagicMock(
        id="sess-1",
        status="in_progress",
        generated_questions=QUESTIONS,
        interview_metadata=metadata,
    )


def _api_client():
    client = MagicMock()
    for name in (
        "update_status",
        "save_transcript",
        "save_evaluation",
        "save_final_summary",
        "save_interview_metadata",
    ):
        setattr(client, name, AsyncMock(return_value=True))
    return client


def _policy():
    return PipecatInterviewPolicy(
        "sess-1",
        evaluator=MagicMock(),
        llm_client=MagicMock(),
        api_client=_api_client(),
        speech_output=AsyncMock(),
    )


async def _start(policy, session, saved_evaluations):
    with patch(
        "src.screening_pipeline.pipecat_policy.interview_session_repo.get_by_id",
        AsyncMock(return_value=session),
    ), patch(
        "src.screening_pipeline.pipecat_policy.interview_session_repo.get_saved_evaluations",
        AsyncMock(return_value=saved_evaluations),
    ), patch(
        "src.screening_pipeline.pipecat_policy.is_candidate_present", return_value=True
    ):
        await policy.start()


def _spoken(policy):
    return [c.args[0] for c in policy.speech_output.await_args_list]


def _saved_transcript(*, q2_asked=False):
    transcript = [
        {"interaction_type": "greeting", "bot_speech": GREETING_TEXT, "candidate_answer": "Yes"},
        {
            "interaction_type": "question",
            "question_id": 1,
            "bot_speech": "Explain sagas.",
            "candidate_answer": "Saga pattern...",
            "follow_ups": [],
        },
    ]
    if q2_asked:
        transcript.append(
            {
                "interaction_type": "question",
                "question_id": 2,
                "bot_speech": "Explain circuit breakers.",
                "candidate_answer": "",
                "follow_ups": [],
            }
        )
    return transcript


@pytest.mark.asyncio
async def test_reconnect_mid_interview_continues_instead_of_greeting_again():
    policy = _policy()
    await _start(policy, _session(_saved_transcript()), [Q1_EVALUATION])

    assert _spoken(policy) == [RESUME_TEXT, "Explain circuit breakers."]
    assert GREETING_TEXT not in _spoken(policy)
    assert policy.analysis_evaluations == [Q1_EVALUATION]
    assert policy.current_question_idx == 1
    # The earlier conversation is kept, so the final transcript has all of it.
    assert [e["interaction_type"] for e in policy.transcript_log] == [
        "greeting", "question", "resume", "question",
    ]


@pytest.mark.asyncio
async def test_the_question_interrupted_by_the_restart_is_asked_again():
    # Question 2 was asked but its answer was never scored.
    policy = _policy()
    await _start(policy, _session(_saved_transcript(q2_asked=True)), [Q1_EVALUATION])

    assert _spoken(policy)[-1] == "Explain circuit breakers."


@pytest.mark.asyncio
async def test_scores_from_an_earlier_attempt_are_not_resumed():
    # A rescheduled attempt starts with a fresh transcript; an evaluation for
    # a question this attempt never asked belongs to the earlier attempt.
    stale = {"question_id": 3, "category": "must_have_matched", "score": 9.0}
    policy = _policy()
    await _start(policy, _session(_saved_transcript()), [stale, Q1_EVALUATION])

    assert policy.analysis_evaluations == [Q1_EVALUATION]


@pytest.mark.asyncio
async def test_nothing_saved_yet_starts_with_the_greeting():
    policy = _policy()
    await _start(policy, _session(), [])

    assert _spoken(policy)[:1] == [GREETING_TEXT]


@pytest.mark.asyncio
async def test_saved_transcript_without_scores_starts_with_the_greeting():
    # The scores could not be read: start over rather than skip questions.
    policy = _policy()
    await _start(policy, _session(_saved_transcript()), [])

    assert _spoken(policy)[:1] == [GREETING_TEXT]


@pytest.mark.asyncio
async def test_final_summary_includes_answers_from_before_the_restart():
    policy = _policy()
    await _start(policy, _session(_saved_transcript()), [Q1_EVALUATION])

    with patch(
        "src.screening_pipeline.pipecat_policy.persist_interview_close", AsyncMock()
    ) as close:
        await policy.end_interview("meeting_ended")

    evaluations, transcript_log = close.await_args.args[2], close.await_args.args[3]
    assert Q1_EVALUATION in evaluations
    assert transcript_log[1]["candidate_answer"] == "Saga pattern..."


@pytest.mark.asyncio
async def test_each_finished_question_saves_the_transcript_after_its_score():
    policy = _policy()
    order = []
    api = policy.api_client
    api.save_transcript.side_effect = lambda *_: order.append("qa")
    api.save_evaluation.side_effect = lambda *_: order.append("evaluation")
    api.save_interview_metadata.side_effect = lambda *_: order.append("transcript")
    policy.transcript_log = [
        {
            "interaction_type": "question",
            "question_id": 1,
            "bot_speech": "Explain sagas.",
            "candidate_answer": "Saga pattern...",
            "follow_ups": [],
        }
    ]

    policy._persist_question({"question_id": 1}, Q1_EVALUATION)
    # A later turn must not change what was saved for this question.
    policy.transcript_log[0]["candidate_answer"] = "changed"
    await policy._flush_pending_persist()

    assert order == ["qa", "evaluation", "transcript"]
    snapshot = api.save_interview_metadata.await_args.args[0]
    assert snapshot[0]["question_id"] == 1
    assert snapshot[0]["candidate_answer"] == "Saga pattern..."
