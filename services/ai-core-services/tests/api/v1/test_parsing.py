from unittest.mock import AsyncMock, patch

import pytest

from src.parsing.schemas import ParsedJDData, ParsedResumeData


@pytest.mark.asyncio
async def test_parse_resume_endpoint_success(client):
    with patch(
        "src.api.v1.parsing.resume_parser.parse_s3_file",
        new_callable=AsyncMock,
        return_value=ParsedResumeData(primary_skills=["Python"]),
    ):
        response = await client.post(
            "/internal/v1/parse/resume",
            json={"resume_name": "a.pdf", "resume_path": "resumes/a.pdf"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["parsed_resume"]["primary_skills"] == ["Python"]


@pytest.mark.asyncio
async def test_parse_resume_endpoint_error(client):
    with patch(
        "src.api.v1.parsing.resume_parser.parse_s3_file",
        new_callable=AsyncMock,
        side_effect=RuntimeError("s3 missing"),
    ):
        response = await client.post(
            "/internal/v1/parse/resume",
            json={"resume_name": "b.pdf", "resume_path": "resumes/b.pdf"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "error"
    assert "s3 missing" in body["error_message"]


@pytest.mark.asyncio
async def test_parse_jd_endpoint_success(client):
    with patch(
        "src.api.v1.parsing.jd_parser.parse_jd_text",
        new_callable=AsyncMock,
        return_value=ParsedJDData(title="Engineer"),
    ):
        response = await client.post(
            "/internal/v1/parse/jd",
            json={"title": "Engineer", "description": "Build APIs"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["parsed_jd"]["title"] == "Engineer"
