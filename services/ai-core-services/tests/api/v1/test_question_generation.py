from unittest.mock import AsyncMock, patch

import pytest

from src.parsing.schemas import ParsedJDData
from src.question_generation.schemas import GenerateQuestionsResponse, GeneratedQuestion


@pytest.mark.asyncio
async def test_generate_questions_endpoint_success(client):
    mock_response = GenerateQuestionsResponse(
        interview_session_id="sess-1",
        status="success",
        questions=[
            GeneratedQuestion(
                id=1,
                category="must_have_matched",
                skill_focus="Python",
                question="Explain list vs tuple?",
                expected_keywords=["mutable"],
                answer_depth="aware",
            )
        ],
        count=1,
    )

    with patch(
        "src.api.v1.question_generation.question_generator.generate",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        response = await client.post(
            "/internal/v1/screening/questions/generate",
            json={
                "interview_session_id": "sess-1",
                "parsed_jd": ParsedJDData(title="Engineer").model_dump(),
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["count"] == 1


@pytest.mark.asyncio
async def test_generate_questions_endpoint_error_body(client):
    mock_response = GenerateQuestionsResponse(
        interview_session_id="sess-2",
        status="error",
        error_message="LLM failed",
    )

    with patch(
        "src.api.v1.question_generation.question_generator.generate",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        response = await client.post(
            "/internal/v1/screening/questions/generate",
            json={
                "interview_session_id": "sess-2",
                "parsed_jd": ParsedJDData(title="Engineer").model_dump(),
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "error"
    assert body["error_message"] == "LLM failed"
