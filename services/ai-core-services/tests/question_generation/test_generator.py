from unittest.mock import AsyncMock, MagicMock

import pytest

from src.parsing.schemas import ParsedJDData
from src.question_generation.generator import QuestionGenerator
from src.question_generation.schemas import GenerateQuestionsRequest, GeneratedQuestion


@pytest.mark.asyncio
async def test_question_generator_success_with_mocked_llm():
    llm = MagicMock()
    llm.openai_chat_generate = AsyncMock(
        return_value=MagicMock(
            response=[
                {
                    "id": 1,
                    "category": "must_have_matched",
                    "skill_focus": "Python",
                    "question": "Describe async/await.",
                    "expected_keywords": ["event loop"],
                    "answer_depth": "partial_depth",
                }
            ]
        )
    )
    generator = QuestionGenerator(llm_client=llm)
    request = GenerateQuestionsRequest(
        interview_session_id="session-1",
        parsed_jd=ParsedJDData(title="Engineer"),
    )

    result = await generator.generate(request)

    assert result.status == "success"
    assert result.count == 1
    assert isinstance(result.questions[0], GeneratedQuestion)
    llm.openai_chat_generate.assert_awaited_once()


@pytest.mark.asyncio
async def test_question_generator_error_on_llm_failure():
    llm = MagicMock()
    llm.openai_chat_generate = AsyncMock(side_effect=RuntimeError("ollama down"))
    generator = QuestionGenerator(llm_client=llm)
    request = GenerateQuestionsRequest(
        interview_session_id="session-2",
        parsed_jd=ParsedJDData(title="Engineer"),
    )

    result = await generator.generate(request)

    assert result.status == "error"
    assert "ollama down" in result.error_message
