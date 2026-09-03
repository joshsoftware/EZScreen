from unittest.mock import AsyncMock, patch

import pytest

from src.parsing.schemas import ParsedJDData, ParsedResumeData


@pytest.mark.asyncio
async def test_match_endpoint_success(client):
    mock_result = {
        "score_breakdown": {
            "raw_must_have_skills": 40.0,
            "raw_good_to_have_skills": 20.0,
            "raw_experience": 30.0,
            "raw_qualifications": 10.0,
            "skills_score": 10.0,
            "experience_score": 10.0,
            "qualifications_score": 10.0,
        },
        "match_score": 10.0,
        "reasoning": ["Strong fit."],
        "strengths": ["Python"],
        "concerns": ["No major concerns identified."],
        "matched_skills": {"must_have": ["Python"], "good_to_have": []},
        "missing_skills": {"must_have": [], "good_to_have": []},
        "must_have_experience": [],
        "good_to_have_experience": [],
        "qualification_match": True,
        "experience_match": True,
    }

    with patch(
        "src.api.v1.matching.job_fit_matcher.analyze_fit",
        new_callable=AsyncMock,
        return_value=mock_result,
    ):
        response = await client.post(
            "/internal/v1/match/resume-jd",
            json={
                "application_id": "app-1",
                "job_id": "job-1",
                "parsed_resume": ParsedResumeData(primary_skills=["Python"]).model_dump(),
                "parsed_jd": ParsedJDData(title="Engineer").model_dump(),
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["application_id"] == "app-1"
    assert body["job_fit_analysis"]["match_score"] == 10.0


@pytest.mark.asyncio
async def test_match_endpoint_error(client):
    with patch(
        "src.api.v1.matching.job_fit_matcher.analyze_fit",
        new_callable=AsyncMock,
        side_effect=ValueError("LLM returned invalid matching JSON"),
    ):
        response = await client.post(
            "/internal/v1/match/resume-jd",
            json={
                "application_id": "app-2",
                "job_id": "job-2",
                "parsed_resume": ParsedResumeData().model_dump(),
                "parsed_jd": ParsedJDData().model_dump(),
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "error"
    assert "invalid matching JSON" in body["error_message"]
