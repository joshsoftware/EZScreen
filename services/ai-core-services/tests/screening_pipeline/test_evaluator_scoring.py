from unittest.mock import AsyncMock, MagicMock

import pytest

from src.screening_pipeline.evaluator import AnswerEvaluator


@pytest.mark.asyncio
async def test_evaluator_combines_python_keyword_coverage_with_llm_quality():
    llm_client = MagicMock()
    llm_client.openai_chat_generate = AsyncMock(
        return_value=MagicMock(
            response=(
                '{"answer_quality_score": 8, "decision": "NEXT_QUESTION", '
                '"feedback": "Good conceptual explanation."}'
            )
        )
    )
    evaluator = AnswerEvaluator(llm_client)

    result = await evaluator.evaluate_answer(
        current_question="What is Docker?",
        transcript="Docker packages an application and its dependencies.",
        expected_keywords="Docker, container",
        answer_depth="partial_depth",
    )

    assert result["keywords_found"] == ["Docker"]
    assert result["keywords_missing"] == ["container"]
    assert result["coverage_percent"] == 50
    assert result["keyword_match_score"] == 5.0
    assert result["answer_quality_score"] == 8.0
    assert result["score"] == 6
    assert result["decision"] == "NEXT_QUESTION"
