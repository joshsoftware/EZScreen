from src.job_fit_analysis.score_calculator import recalculate_scores


def _base_match_result(
    matched_must_have=None,
    matched_good_to_have=None,
    must_have_exp=None,
    good_to_have_exp=None,
    raw_qualifications=10.0,
):
    return {
        "score_breakdown": {"raw_qualifications": raw_qualifications},
        "matched_skills": {
            "must_have": matched_must_have or ["Java", "Python"],
            "good_to_have": matched_good_to_have or ["Docker"],
        },
        "missing_skills": {"must_have": [], "good_to_have": []},
        "must_have_experience": must_have_exp
        or [
            {"skill": "Java", "skill_experience_ratio": 1.0},
            {"skill": "Python", "skill_experience_ratio": 0.5},
        ],
        "good_to_have_experience": good_to_have_exp
        or [{"skill": "Docker", "skill_experience_ratio": 1.0}],
    }


def test_recalculate_scores_perfect_match():
    result = _base_match_result(
        matched_must_have=["Java", "Python"],
        matched_good_to_have=["Docker"],
        must_have_exp=[
            {"skill": "Java", "skill_experience_ratio": 1.0},
            {"skill": "Python", "skill_experience_ratio": 1.0},
        ],
    )

    recalculate_scores(result)

    assert result["score_breakdown"]["raw_must_have_skills"] == 40.0
    assert result["score_breakdown"]["raw_good_to_have_skills"] == 20.0
    assert result["score_breakdown"]["raw_experience"] == 30.0
    assert result["match_score"] == 10.0
    assert result["experience_match"] is True


def test_recalculate_scores_partial_must_have_skills():
    result = _base_match_result(
        matched_must_have=["Java"],
        matched_good_to_have=[],
        must_have_exp=[
            {"skill": "Java", "skill_experience_ratio": 1.0},
            {"skill": "Python", "skill_experience_ratio": 0.0},
        ],
        good_to_have_exp=[],
    )

    recalculate_scores(result)

    assert result["score_breakdown"]["raw_must_have_skills"] == 20.0
    assert result["score_breakdown"]["raw_good_to_have_skills"] == 20.0
    assert result["score_breakdown"]["raw_experience"] == 20.0
    assert result["experience_match"] is True


def test_recalculate_scores_experience_below_threshold():
    result = _base_match_result(
        must_have_exp=[
            {"skill": "Java", "skill_experience_ratio": 0.25},
            {"skill": "Python", "skill_experience_ratio": 0.25},
        ],
        good_to_have_exp=[{"skill": "Docker", "skill_experience_ratio": 0.0}],
    )

    recalculate_scores(result)

    assert result["score_breakdown"]["raw_experience"] == 5.0
    assert result["experience_match"] is False


def test_recalculate_scores_creates_score_breakdown_if_missing():
    result = {"matched_skills": {"must_have": [], "good_to_have": []}}

    recalculate_scores(result)

    assert "score_breakdown" in result
    assert "match_score" in result
