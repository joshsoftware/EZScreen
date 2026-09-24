from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.screening_pipeline.persistence import (
    build_completed_question_payload,
    persist_interview_close,
    persist_qa_and_evaluation,
)


def test_build_completed_question_payload_builds_qa_entry_and_evaluation():
    with patch(
        "src.screening_pipeline.persistence.AnswerEvaluator.build_qa_entry",
        return_value={"question_id": 1},
    ), patch(
        "src.screening_pipeline.persistence.AnswerEvaluator.build_evaluation_block",
        return_value={"question_id": 1, "score": 8},
    ):
        qa_entry, evaluation = build_completed_question_payload(
            question_obj={"id": 1},
            current_q="What is Docker?",
            transcript="Containers",
            primary_eval={"score": 8},
            current_eval={"score": 8},
            question_number=1,
            follow_ups=None,
        )

    assert qa_entry == {"question_id": 1}
    assert evaluation["score"] == 8


@pytest.mark.asyncio
async def test_persist_qa_and_evaluation_saves_transcript_then_evaluation():
    api_client = MagicMock()
    api_client.save_transcript = AsyncMock()
    api_client.save_evaluation = AsyncMock()

    await persist_qa_and_evaluation(
        api_client, {"question_id": 1}, {"question_id": 1, "score": 8}
    )

    api_client.save_transcript.assert_awaited_once_with({"question_id": 1})
    api_client.save_evaluation.assert_awaited_once_with({"question_id": 1, "score": 8})


@pytest.mark.asyncio
async def test_persist_qa_and_evaluation_does_not_raise_when_core_api_rejects():
    api_client = MagicMock()
    api_client.save_transcript = AsyncMock(return_value=True)
    api_client.save_evaluation = AsyncMock(return_value=False)

    # SessionApiClient already logs/handles HTTP failures internally and
    # returns False rather than raising; a background persist task must not
    # raise either, since nothing awaits its result inline.
    await persist_qa_and_evaluation(
        api_client, {"question_id": 1}, {"question_id": 1, "score": 8}
    )


@pytest.mark.asyncio
async def test_persist_interview_close_calls_summary_and_metadata():
    api_client = MagicMock()
    api_client.save_final_summary = AsyncMock()
    api_client.save_interview_metadata = AsyncMock()

    llm_client = MagicMock()
    llm_client.openai_chat_generate = AsyncMock(return_value=MagicMock(response='{"interview_summary": ["point 1"]}'))
    await persist_interview_close(api_client, llm_client, [{"score": 7, "category": "must_have_matched"}], [{"bot_speech": "hi"}])

    api_client.save_final_summary.assert_awaited_once()
    api_client.save_interview_metadata.assert_awaited_once()


@pytest.mark.asyncio
async def test_persist_interview_close_saves_metadata_when_no_answer_was_scored():
    api_client = MagicMock()
    api_client.save_final_summary = AsyncMock()
    api_client.save_interview_metadata = AsyncMock()

    await persist_interview_close(api_client, MagicMock(), [], [{"bot_speech": "hi"}])

    api_client.save_final_summary.assert_not_awaited()
    api_client.save_interview_metadata.assert_awaited_once()
