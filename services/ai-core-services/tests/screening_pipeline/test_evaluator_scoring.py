from unittest.mock import AsyncMock, MagicMock

import pytest

from src.screening_pipeline.evaluator import AnswerEvaluator


@pytest.mark.asyncio
async def test_evaluator_combines_python_keyword_coverage_with_llm_quality():
    llm_client = MagicMock()
    llm_client.openai_chat_generate = AsyncMock(
        return_value=MagicMock(
            response=(
                '{"intent": "ANSWERING", "response": "", '
                '"answer_quality_score": 8, "decision": "NEXT_QUESTION", '
                '"feedback": "Good conceptual explanation."}'
            )
        )
    )
    evaluator = AnswerEvaluator(llm_client)

    result = await evaluator.classify_and_evaluate(
        current_question="What is Docker?",
        transcript="Docker packages an application and its dependencies.",
        expected_keywords="Docker, container",
        answer_depth="partial_depth",
    )

    assert result["intent"] == "ANSWERING"
    assert result["keywords_found"] == ["Docker"]
    assert result["keywords_missing"] == ["container"]
    assert result["coverage_percent"] == 50
    assert result["keyword_match_score"] == 5.0
    assert result["answer_quality_score"] == 8.0
    assert result["score"] == 6
    assert result["decision"] == "NEXT_QUESTION"
    llm_client.openai_chat_generate.assert_awaited_once()


@pytest.mark.asyncio
async def test_classify_and_evaluate_skips_scoring_for_non_answering_intent():
    llm_client = MagicMock()
    llm_client.openai_chat_generate = AsyncMock(
        return_value=MagicMock(
            response='{"intent": "CLARIFICATION", "response": "Sure, let me repeat that."}'
        )
    )
    evaluator = AnswerEvaluator(llm_client)

    result = await evaluator.classify_and_evaluate(
        current_question="What is Docker?",
        transcript="Can you repeat that?",
        expected_keywords="Docker, container",
        answer_depth="partial_depth",
    )

    assert result == {"intent": "CLARIFICATION", "response": "Sure, let me repeat that."}
    llm_client.openai_chat_generate.assert_awaited_once()


@pytest.mark.asyncio
async def test_classify_and_evaluate_falls_back_to_answering_on_malformed_json():
    llm_client = MagicMock()
    llm_client.openai_chat_generate = AsyncMock(
        return_value=MagicMock(response="not json")
    )
    evaluator = AnswerEvaluator(llm_client)

    result = await evaluator.classify_and_evaluate(
        current_question="What is Docker?",
        transcript="uh...",
        expected_keywords="Docker, container",
        answer_depth="partial_depth",
    )

    assert result["intent"] == "ANSWERING"
    assert result["decision"] == "ASK_FOLLOW_UP"
    assert result["score"] == 0
