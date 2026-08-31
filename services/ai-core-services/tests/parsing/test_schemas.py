import pytest
from pydantic import ValidationError

from src.parsing.schemas import ParsedJDData, ParsedResumeData, SkillRequirement


def test_parsed_resume_data_defaults():
    resume = ParsedResumeData()
    assert resume.primary_skills == []
    assert resume.secondary_skills == []
    assert resume.skill_experience == []


def test_parsed_jd_data_with_skills():
    jd = ParsedJDData(
        title="Backend Engineer",
        skills={
            "must_have": [SkillRequirement(skill="Python", required_years=3.0)],
            "good_to_have": [SkillRequirement(skill="Docker")],
        },
    )
    assert jd.title == "Backend Engineer"
    assert len(jd.skills.must_have) == 1
    assert jd.skills.must_have[0].required_years == 3.0


def test_match_request_requires_parsed_payloads():
    with pytest.raises(ValidationError):
        ParsedResumeData.model_validate({"primary_skills": "not-a-list"})
