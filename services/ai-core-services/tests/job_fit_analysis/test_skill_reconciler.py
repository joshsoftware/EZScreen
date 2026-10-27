"""Bug-032: skills written in the resume were reported missing, and concerns
contradicted matched skills."""

from src.job_fit_analysis.score_calculator import recalculate_scores
from src.job_fit_analysis.skill_reconciler import mentions_skill, reconcile_skills


def _resume(**overrides):
    resume = {
        "primary_skills": ["React", "JavaScript"],
        "secondary_skills": [],
        "skill_experience": [{"skill": "React", "years": 2.0}],
        "experience": {
            "roles": [
                {
                    "title": "Frontend Developer",
                    "highlights": ["Built dashboards in React and Redux Toolkit."],
                    "highlight_groups": [],
                }
            ]
        },
        "projects": [],
    }
    resume.update(overrides)
    return resume


def _jd(must=(), good=()):
    return {
        "skills": {
            "must_have": [{"skill": s, "required_years": y} for s, y in must],
            "good_to_have": [{"skill": s, "required_years": y} for s, y in good],
        }
    }


def _result(matched=(), missing=(), concerns=()):
    return {
        "matched_skills": {"must_have": list(matched), "good_to_have": []},
        "missing_skills": {"must_have": list(missing), "good_to_have": []},
        "must_have_experience": [
            {"skill": s, "required_years": None, "candidate_years": 0.0, "skill_experience_ratio": 0.0, "meets_requirement": False}
            for s in missing
        ]
        + [
            {"skill": s, "required_years": None, "candidate_years": 1.0, "skill_experience_ratio": 1.0, "meets_requirement": True}
            for s in matched
        ],
        "good_to_have_experience": [],
        "concerns": list(concerns),
        "score_breakdown": {"raw_qualifications": 10.0},
    }


def test_skill_in_role_bullets_is_moved_to_matched_and_rescored():
    """Atharv Kardile: Redux used in the work, but shown as missing."""
    result = _result(matched=["React"], missing=["Redux"])
    reconcile_skills(result, _resume(), _jd(must=[("React", None), ("Redux", None)]))
    recalculate_scores(result)

    assert result["matched_skills"]["must_have"] == ["React", "Redux"]
    assert result["missing_skills"]["must_have"] == []
    assert result["score_breakdown"]["raw_must_have_skills"] == 40.0


def test_skill_in_project_tech_stack_and_internship_counts():
    """Akshay Dhokale: MySQL and MongoDB in the resume, reported missing."""
    resume = _resume(
        projects=[{"name": "Shop", "tech_stack": ["Node.js", "MongoDB"], "highlights": []}],
        experience={"roles": [{"title": "Backend Intern", "is_internship": True, "highlights": ["Wrote MySQL reports."]}]},
    )
    result = _result(missing=["MySQL", "MongoDB"])
    reconcile_skills(result, resume, _jd(must=[("MySQL", None), ("MongoDB", None)]))

    assert result["matched_skills"]["must_have"] == ["MySQL", "MongoDB"]
    assert all(e["meets_requirement"] for e in result["must_have_experience"])


def test_alias_and_parenthesised_names():
    """Sohan Waghmare: EKS in the resume, shown as missing."""
    resume = _resume(experience={"roles": [{"highlights": ["Ran services on Amazon EKS with Helm."]}]})
    result = _result(missing=["Kubernetes (EKS)"])
    reconcile_skills(result, resume, _jd(must=[("Kubernetes (EKS)", None)]))
    assert result["matched_skills"]["must_have"] == ["Kubernetes (EKS)"]


def test_rest_api_work_counts_as_api_integration():
    """Kirti: REST APIs present, API Integrations shown missing."""
    resume = _resume(experience={"roles": [{"highlights": ["Integrated third-party REST APIs for payments."]}]})
    result = _result(missing=["API Integrations"])
    reconcile_skills(result, resume, _jd(must=[("API Integrations", None)]))
    assert result["matched_skills"]["must_have"] == ["API Integrations"]


def test_absent_skill_stays_missing_and_no_false_matches():
    resume = _resume(primary_skills=["JavaScript", "Google Analytics"], experience={"roles": []})
    result = _result(missing=["Java", "Go", "C"])
    reconcile_skills(result, resume, _jd(must=[("Java", None), ("Go", None), ("C", None)]))

    assert result["matched_skills"]["must_have"] == []
    assert result["missing_skills"]["must_have"] == ["Java", "Go", "C"]


def test_llm_matches_are_never_demoted():
    """Hemant Deshmukh: JD "JavaScript (ES6+)" matched from plain "JavaScript" stays matched."""
    result = _result(matched=["JavaScript (ES6+)"])
    reconcile_skills(result, _resume(), _jd(must=[("JavaScript (ES6+)", None)]))
    assert result["matched_skills"]["must_have"] == ["JavaScript (ES6+)"]


def test_required_years_still_apply_to_promoted_skills():
    result = _result(missing=["React"])
    reconcile_skills(result, _resume(), _jd(must=[("React", 4.0)]))
    entry = result["must_have_experience"][0]

    assert result["matched_skills"]["must_have"] == ["React"]
    assert entry["candidate_years"] == 2.0
    assert entry["skill_experience_ratio"] == 0.5
    assert entry["meets_requirement"] is False


def test_every_jd_skill_has_exactly_one_experience_entry():
    result = _result(matched=["React"], missing=[])
    result["must_have_experience"].append(dict(result["must_have_experience"][0]))  # LLM duplicate
    reconcile_skills(result, _resume(), _jd(must=[("React", None), ("Kafka", None)]))

    assert [e["skill"] for e in result["must_have_experience"]] == ["React", "Kafka"]
    assert result["missing_skills"]["must_have"] == ["Kafka"]


def test_concerns_contradicting_matched_skills_are_dropped():
    """Chaitanya Nagesh: MongoDB matched, but a concern said it was lacking."""
    resume = _resume(skill_experience=[{"skill": "MongoDB", "years": 1.5}])
    result = _result(
        matched=["MongoDB"],
        missing=["Kafka"],
        concerns=[
            "The candidate lacks MongoDB experience.",
            "MongoDB is not found in the resume.",
            "Missing critical must-have skill: Kafka.",
            "No exposure to Kafka or MongoDB clustering.",
        ],
    )
    reconcile_skills(result, resume, _jd(must=[("MongoDB", None), ("Kafka", None)]))

    assert result["concerns"] == [
        "Missing critical must-have skill: Kafka.",
        "No exposure to Kafka or MongoDB clustering.",  # also about a truly missing skill
    ]


def test_all_concerns_dropped_leaves_the_default_line():
    resume = _resume(skill_experience=[{"skill": "React", "years": 2.0}])
    result = _result(matched=["React"], concerns=["React is missing from the resume."])
    reconcile_skills(result, resume, _jd(must=[("React", None)]))
    assert result["concerns"] == ["No major concerns identified."]


def test_word_boundaries():
    assert mentions_skill("Java", "Java 17, Spring Boot")
    assert not mentions_skill("Java", "JavaScript and TypeScript")
    assert mentions_skill("C++", "Wrote C++ services")
    assert not mentions_skill("C++", "Wrote C services")
    assert mentions_skill("REST APIs", "Built a REST API")
    assert mentions_skill("Node.js", "NodeJS microservices")
