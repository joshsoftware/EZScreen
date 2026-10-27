"""An answer is still scored when the interview ends during its follow-up.

Live test: the candidate answered Q1 briefly, the bot asked a follow-up, the
candidate went quiet and the bot ended on silence — 0 answers were scored.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.screening_pipeline.pipecat_policy import PipecatInterviewPolicy

QUESTION = {"id": 1, "question": "HashMap vs ConcurrentHashMap?", "category": "must_have_matched"}


def _policy():
    api_client = MagicMock()
    api_client.update_status = AsyncMock(return_value=True)
    policy = PipecatInterviewPolicy(
        "sess-follow-up",
        evaluator=MagicMock(),
        llm_client=MagicMock(),
        api_client=api_client,
        speech_output=AsyncMock(),
    )
    policy.is_active = True
    policy._leave_bot_after_close = AsyncMock()
    policy.transcript_log = [
        {
            "interaction_type": "question",
            "question_id": 1,
            "bot_speech": QUESTION["question"],
            "candidate_answer": "",
            "follow_ups": [],
        },
    ]
    return policy


async def _answer_then_follow_up(policy):
    await policy._handle_answer(
        QUESTION,
        QUESTION["question"],
        "ConcurrentHashMap uses locking.",
        {"decision": "ASK_FOLLOW_UP", "score": 4, "suggested_follow_up": "Can you elaborate?"},
        None,
    )


@pytest.mark.asyncio
async def test_main_answer_is_scored_when_the_interview_ends_on_silence():
    policy = _policy()
    await _answer_then_follow_up(policy)
    # "Are you there?" prompts land on the transcript after the question.
    policy.transcript_log.append({"interaction_type": "silence_prompt", "candidate_answer": ""})

    with patch(
        "src.screening_pipeline.pipecat_policy.persist_qa_and_evaluation", AsyncMock()
    ) as save_question, patch(
        "src.screening_pipeline.pipecat_policy.persist_interview_close", AsyncMock()
    ) as close:
        await policy.end_interview("candidate_silence")

    assert len(policy.analysis_evaluations) == 1
    save_question.assert_awaited_once()
    qa_entry = save_question.await_args.args[1]
    # The unanswered follow-up is left out of the Q&A save (core-api rejects
    # empty answers) but kept in the transcript so HR sees it was asked.
    assert qa_entry.get("follow_ups", []) == []
    assert policy.transcript_log[0]["follow_ups"] == [
        {"candidate_speech": "", "ai_response": "Can you elaborate?"}
    ]
    assert close.await_args.args[2] == policy.analysis_evaluations
    policy.api_client.update_status.assert_awaited_once_with("completed")


@pytest.mark.asyncio
async def test_nothing_extra_is_saved_once_the_follow_up_was_answered():
    policy = _policy()
    policy._ask_next_question = AsyncMock()

    with patch(
        "src.screening_pipeline.pipecat_policy.persist_qa_and_evaluation", AsyncMock()
    ) as save_question, patch(
        "src.screening_pipeline.pipecat_policy.persist_interview_close", AsyncMock()
    ):
        await _answer_then_follow_up(policy)
        await policy._handle_answer(
            QUESTION,
            QUESTION["question"],
            "It locks per bucket.",
            {"decision": "NEXT_QUESTION", "score": 7},
            {"decision": "ASK_FOLLOW_UP", "score": 4},
        )
        await policy.end_interview("candidate_silence")

    assert len(policy.analysis_evaluations) == 1
    save_question.assert_awaited_once()
