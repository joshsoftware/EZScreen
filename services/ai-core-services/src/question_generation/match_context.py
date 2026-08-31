"""Synthetic job-fit context for job-level question banks (no candidate resume)."""

from __future__ import annotations

from typing import Any

from src.parsing.schemas import ParsedJDData


def neutral_job_fit_analysis(parsed_jd: ParsedJDData) -> dict[str, Any]:
    """Build a JD-only match payload so dev's question prompt can run without a candidate."""
    must_have = [skill.skill for skill in parsed_jd.skills.must_have if skill.skill]
    good_to_have = [skill.skill for skill in parsed_jd.skills.good_to_have if skill.skill]

    return {
        "score_breakdown": {
            "raw_must_have_skills": 0.0,
            "raw_good_to_have_skills": 0.0,
            "raw_experience": 0.0,
            "raw_qualifications": 0.0,
            "skills_score": 0.0,
            "experience_score": 0.0,
            "qualifications_score": 0.0,
        },
        "match_score": 0.0,
        "reasoning": [
            "Job-level screening bank: no candidate resume provided.",
            "Generate role-based questions from the JD must-have skills and responsibilities.",
        ],
        "strengths": [],
        "concerns": must_have[:4] or ["Assess core must-have skills for this role."],
        "matched_skills": {"must_have": must_have, "good_to_have": []},
        "missing_skills": {"must_have": [], "good_to_have": good_to_have},
        "must_have_experience": [],
        "good_to_have_experience": [],
        "qualification_match": False,
        "experience_match": False,
    }
