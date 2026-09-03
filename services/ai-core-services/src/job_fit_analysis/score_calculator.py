"""Deterministic score recalculation for job fit analysis.

Pure functions — no I/O. Overrides LLM math to prevent hallucinated scores.
"""


def recalculate_scores(match_result: dict) -> None:
    """Recalculate match scores from matched_skills and experience arrays."""
    if "score_breakdown" not in match_result:
        match_result["score_breakdown"] = {}

    must_have_exp = match_result.get("must_have_experience", [])
    good_to_have_exp = match_result.get("good_to_have_experience", [])

    total_must_have = len(must_have_exp)
    total_good_to_have = len(good_to_have_exp)

    matched_must_have = len(match_result.get("matched_skills", {}).get("must_have", []))
    raw_must_have = (matched_must_have / total_must_have) * 40.0 if total_must_have > 0 else 40.0

    matched_good = len(match_result.get("matched_skills", {}).get("good_to_have", []))
    raw_good_to_have = (matched_good / total_good_to_have) * 20.0 if total_good_to_have > 0 else 20.0

    sum_must_have_ratios = sum(float(skill.get("skill_experience_ratio", 0.0)) for skill in must_have_exp)
    raw_exp_must_have = (sum_must_have_ratios / total_must_have) * 20.0 if total_must_have > 0 else 20.0

    sum_good_ratios = sum(float(skill.get("skill_experience_ratio", 0.0)) for skill in good_to_have_exp)
    raw_exp_good = (sum_good_ratios / total_good_to_have) * 10.0 if total_good_to_have > 0 else 10.0

    raw_exp = raw_exp_must_have + raw_exp_good

    raw_qual = float(match_result.get("score_breakdown", {}).get("raw_qualifications", 10.0))

    match_result["score_breakdown"]["raw_must_have_skills"] = round(raw_must_have, 2)
    match_result["score_breakdown"]["raw_good_to_have_skills"] = round(raw_good_to_have, 2)
    match_result["score_breakdown"]["raw_experience"] = round(raw_exp, 2)
    match_result["score_breakdown"]["raw_qualifications"] = round(raw_qual, 2)

    skills_score = ((raw_must_have + raw_good_to_have) / 60.0) * 10.0
    exp_score = (raw_exp / 30.0) * 10.0
    qual_score = (raw_qual / 10.0) * 10.0

    match_result["score_breakdown"]["skills_score"] = round(skills_score, 2)
    match_result["score_breakdown"]["experience_score"] = round(exp_score, 2)
    match_result["score_breakdown"]["qualifications_score"] = round(qual_score, 2)

    total_raw = raw_must_have + raw_good_to_have + raw_exp + raw_qual
    match_result["match_score"] = round(total_raw / 10.0, 2)

    match_result["experience_match"] = raw_exp >= 20.0
