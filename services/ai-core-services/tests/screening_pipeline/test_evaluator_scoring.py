from unittest.mock import AsyncMock, MagicMock

import pytest

from src.screening_pipeline.evaluator import AnswerEvaluator


def _evaluator_returning(raw_response: str) -> AnswerEvaluator:
    llm_client = MagicMock()
    llm_client.openai_chat_generate = AsyncMock(
        return_value=MagicMock(response=raw_response)
    )
    return AnswerEvaluator(llm_client)


@pytest.mark.asyncio
async def test_evaluator_combines_llm_keyword_coverage_with_llm_quality():
    evaluator = _evaluator_returning(
        '{"intent": "ANSWERING", "response": "", '
        '"keywords_found": ["Docker"], '
        '"answer_quality_score": 8, "decision": "NEXT_QUESTION", '
        '"feedback": "Good conceptual explanation."}'
    )
    llm_client = evaluator.llm_client

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


@pytest.mark.asyncio
async def test_keywords_found_is_restricted_to_expected_keywords():
    evaluator = _evaluator_returning(
        '{"intent": "ANSWERING", "response": "", '
        '"keywords_found": ["docker", "Kubernetes", "container"], '
        '"answer_quality_score": 10, "decision": "NEXT_QUESTION", "feedback": ""}'
    )

    result = await evaluator.classify_and_evaluate(
        current_question="What is Docker?",
        transcript="Docker runs containers.",
        expected_keywords="Docker, container, image, layers",
        answer_depth="partial_depth",
    )

    # "Kubernetes" was never expected, so it is dropped; matching is case-insensitive
    # and the expected list's own spelling is preserved.
    assert result["keywords_found"] == ["Docker", "container"]
    assert result["keywords_missing"] == ["image", "layers"]
    assert result["coverage_percent"] == 50
    assert result["keyword_match_score"] == 5.0
    assert result["score"] == 8


@pytest.mark.asyncio
async def test_missing_keywords_found_field_scores_zero_keyword_coverage():
    evaluator = _evaluator_returning(
        '{"intent": "ANSWERING", "response": "", '
        '"answer_quality_score": 8, "decision": "NEXT_QUESTION", "feedback": ""}'
    )

    result = await evaluator.classify_and_evaluate(
        current_question="What is Docker?",
        transcript="Docker packages apps.",
        expected_keywords="Docker, container",
        answer_depth="partial_depth",
    )

    assert result["keywords_found"] == []
    assert result["keywords_missing"] == ["Docker", "container"]
    assert result["coverage_percent"] == 0
    assert result["score"] == 4
    assert result["decision"] == "ASK_FOLLOW_UP"


@pytest.mark.asyncio
async def test_no_expected_keywords_uses_answer_quality_for_both_halves():
    evaluator = _evaluator_returning(
        '{"intent": "ANSWERING", "response": "", "keywords_found": [], '
        '"answer_quality_score": 7, "decision": "ASK_FOLLOW_UP", "feedback": ""}'
    )

    result = await evaluator.classify_and_evaluate(
        current_question="What is Docker?",
        transcript="Docker packages apps.",
        expected_keywords="",
        answer_depth="partial_depth",
    )

    assert result["keyword_match_score"] == 7.0
    assert result["coverage_percent"] == 100
    assert result["score"] == 7
    assert result["decision"] == "NEXT_QUESTION"
