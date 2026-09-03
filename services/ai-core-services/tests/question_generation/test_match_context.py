from src.parsing.schemas import JDSkills, ParsedJDData, SkillRequirement
from src.question_generation.match_context import neutral_job_fit_analysis


def test_neutral_job_fit_analysis_uses_jd_skills():
    jd = ParsedJDData(
        title="Backend Engineer",
        skills=JDSkills(
            must_have=[SkillRequirement(skill="Python"), SkillRequirement(skill="SQL")],
            good_to_have=[SkillRequirement(skill="Redis")],
        ),
    )

    result = neutral_job_fit_analysis(jd)

    assert result["match_score"] == 0.0
    assert result["matched_skills"]["must_have"] == ["Python", "SQL"]
    assert result["missing_skills"]["good_to_have"] == ["Redis"]
    assert "Job-level screening bank" in result["reasoning"][0]
