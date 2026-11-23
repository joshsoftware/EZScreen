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
from src.screening_pipeline.prompts import GREETING_TEXT, RESUME_REANSWER_TEXT, RESUME_TEXT

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

    # Disconnected after Q1 was finished (Q2 not asked yet): just continue.
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

    assert _spoken(policy) == [GREETING_TEXT]


@pytest.mark.asyncio
async def test_saved_transcript_without_scores_starts_with_the_greeting():
    # The scores could not be read: start over rather than skip questions.
    policy = _policy()
    await _start(policy, _session(_saved_transcript()), [])

    assert _spoken(policy) == [GREETING_TEXT]


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


# --- Bug-50: an answer saved just before the restart is scored, not asked again ---

def _transcript_with_unscored_q2(answer="Circuit breakers stop calls to a failing service."):
    return [
        {"interaction_type": "greeting", "bot_speech": GREETING_TEXT, "candidate_answer": "Ready."},
        {"interaction_type": "question", "question_id": 1, "bot_speech": "Explain sagas.",
         "candidate_answer": "Sagas are...", "follow_ups": []},
        {"interaction_type": "question", "question_id": 2, "bot_speech": "Explain circuit breakers.",
         "candidate_answer": answer, "follow_ups": []},
    ]


def _spoken_texts(policy):
    return [call.args[0] for call in policy.speech_output.await_args_list]


@pytest.mark.asyncio
async def test_answered_but_unscored_question_is_scored_not_asked_again():
    """Anjali's screening: after "Sorry about that, we got disconnected" the
    bot asked question 12 again although she had already answered it."""
    policy = _policy()
    policy.evaluator.classify_and_evaluate = AsyncMock(
        return_value={"intent": "ANSWERING", "score": 6, "decision": "NEXT_QUESTION", "feedback": "ok"}
    )
    await _start(policy, _session(_transcript_with_unscored_q2()), [Q1_EVALUATION])

    # Disconnected after the answer: "we got disconnected", then Q3, not Q2 again.
    assert _spoken_texts(policy) == [RESUME_TEXT, "Explain Kafka ordering."]
    policy.evaluator.classify_and_evaluate.assert_awaited_once()
    assert policy.evaluator.classify_and_evaluate.await_args.kwargs["transcript"].startswith("Circuit breakers")
    assert [e["question_id"] for e in policy.analysis_evaluations] == [1, 2]
    await policy._flush_pending_persist()
    policy.api_client.save_evaluation.assert_awaited()  # the new score is saved
    await policy.end_interview("test")


@pytest.mark.asyncio
async def test_if_the_saved_answer_cannot_be_scored_the_question_is_asked_again():
    policy = _policy()
    policy.evaluator.classify_and_evaluate = AsyncMock(side_effect=RuntimeError("llm down"))
    await _start(policy, _session(_transcript_with_unscored_q2()), [Q1_EVALUATION])

    assert _spoken_texts(policy) == [RESUME_REANSWER_TEXT, "Explain circuit breakers."]
    await policy.end_interview("test")


@pytest.mark.asyncio
async def test_a_question_with_no_saved_answer_is_still_asked_again():
    policy = _policy()
    policy.evaluator.classify_and_evaluate = AsyncMock()
    await _start(policy, _session(_transcript_with_unscored_q2(answer="")), [Q1_EVALUATION])

    policy.evaluator.classify_and_evaluate.assert_not_awaited()
    # Cut off mid-answer: the candidate is asked to answer it again.
    assert _spoken_texts(policy) == [RESUME_REANSWER_TEXT, "Explain circuit breakers."]
    await policy.end_interview("test")


def test_the_two_reconnect_messages():
    assert RESUME_TEXT == "Sorry about that, we got disconnected."
    assert RESUME_REANSWER_TEXT == (
        "Sorry about that, we got disconnected, and your last answer wasn't recorded properly. "
        "Could you please answer this question again?"
    )
