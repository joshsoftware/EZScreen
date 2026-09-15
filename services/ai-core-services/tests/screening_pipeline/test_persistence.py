from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.screening_pipeline.persistence import (
    persist_completed_question,
    persist_interview_close,
)


@pytest.mark.asyncio
async def test_persist_completed_question_saves_transcript_and_eval():
    api_client = MagicMock()
    api_client.save_transcript = AsyncMock()
    api_client.save_evaluation = AsyncMock(return_value=True)
    evaluations: list = []

    with patch(
        "src.screening_pipeline.persistence.AnswerEvaluator.build_qa_entry",
        return_value={"question_id": 1},
    ), patch(
        "src.screening_pipeline.persistence.AnswerEvaluator.build_evaluation_block",
        return_value={"question_id": 1, "score": 8},
    ):
        result = await persist_completed_question(
            api_client,
            evaluations,
            question_obj={"id": 1},
            current_q="What is Docker?",
            transcript="Containers",
            primary_eval={"score": 8},
            current_eval={"score": 8},
            question_number=1,
            follow_ups=None,
        )

    assert result["score"] == 8
    assert len(evaluations) == 1
    api_client.save_transcript.assert_awaited_once()
    api_client.save_evaluation.assert_awaited_once()


@pytest.mark.asyncio
async def test_persist_completed_question_excludes_evaluation_that_core_api_rejects():
    api_client = MagicMock()
    api_client.save_transcript = AsyncMock(return_value=True)
    api_client.save_evaluation = AsyncMock(return_value=False)
    evaluations: list = []

    with patch(
        "src.screening_pipeline.persistence.AnswerEvaluator.build_qa_entry",
        return_value={"question_id": 1},
    ), patch(
        "src.screening_pipeline.persistence.AnswerEvaluator.build_evaluation_block",
        return_value={"question_id": 1, "score": 8},
    ):
        result = await persist_completed_question(
            api_client,
            evaluations,
            question_obj={"id": 1},
            current_q="What is Docker?",
            transcript="Containers",
            primary_eval={"score": 8},
            current_eval={"score": 8},
            question_number=1,
            follow_ups=None,
        )

    assert result is None
    assert evaluations == []


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
