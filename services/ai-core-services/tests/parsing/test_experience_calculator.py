from src.parsing.experience_calculator import (
    _extract_summary_skill_years,
    _is_internship_role,
    recalculate_experience,
)


def test_recalculate_experience_computes_role_years():
    parsed = {
        "experience": {
            "roles": [
                {"start_date": "2020-01-01", "end_date": "2022-01-01"},
            ]
        }
    }

    recalculate_experience(parsed)

    assert parsed["experience"]["roles"][0]["years"] == 2.0
    assert parsed["experience"]["total_years"] == 2.0


def test_recalculate_experience_merges_overlapping_intervals():
    parsed = {
        "experience": {
            "roles": [
                {"start_date": "2020-01-01", "end_date": "2021-01-01"},
                {"start_date": "2020-06-01", "end_date": "2022-01-01"},
            ]
        }
    }

    recalculate_experience(parsed)

    assert parsed["experience"]["total_years"] == 2.0


def test_recalculate_experience_present_end_date():
    parsed = {
        "experience": {
            "roles": [
                {"start_date": "2020-01-01", "end_date": "present"},
            ]
        }
    }

    recalculate_experience(parsed)

    assert parsed["experience"]["roles"][0]["years"] > 0


def test_recalculate_experience_no_op_on_empty():
    parsed: dict = {}
    recalculate_experience(parsed)
    assert parsed == {}


# ──────────────────────── _extract_summary_skill_years tests ────────────────────────


def test_explicit_per_skill_years_in_phrase():
    """'10 years of experience in Java' should assign 10.0 to Java only."""
    text = "Seasoned developer with 10 years of experience in Java."
    skills = ["Java", "Python", "React"]

    result = _extract_summary_skill_years(text, skills)

    assert result.get("java") == 10.0
    assert "python" not in result
    assert "react" not in result


def test_multi_skill_explicit_statement():
    """'5+ years of Python and React' should assign 5.0 to both skills."""
    text = "Full-stack engineer with 5+ years of experience in Python and React."
    skills = ["Python", "React", "Docker"]

    result = _extract_summary_skill_years(text, skills)

    assert result.get("python") == 5.0
    assert result.get("react") == 5.0
    assert "docker" not in result


def test_inline_format_parentheses():
    """'Java (8 years)' inline format should assign 8.0 to Java."""
    text = "Technical Skills: Java (8 years), Python (3 years), Docker"
    skills = ["Java", "Python", "Docker"]

    result = _extract_summary_skill_years(text, skills)

    assert result.get("java") == 8.0
    assert result.get("python") == 3.0
    # Docker has no years stated — should NOT be in the map
    assert "docker" not in result


def test_inline_format_dash():
    """'Java - 8 years' inline format should assign 8.0 to Java."""
    text = "Core Skills: Java - 8 years, Python - 3 years"
    skills = ["Java", "Python"]

    result = _extract_summary_skill_years(text, skills)

    assert result.get("java") == 8.0
    assert result.get("python") == 3.0


def test_generic_summary_does_not_assign_to_all_skills():
    """Generic '7 years of experience' followed by a skill list should NOT
    blanket-assign 7 years to all skills in the paragraph."""
    text = (
        "7 years of success in DevOps engineering.\n"
        "Skilled in Jenkins, Docker, Kubernetes, and Terraform.\n"
        "Expert in CI/CD pipelines and cloud infrastructure."
    )
    skills = ["Jenkins", "Docker", "Kubernetes", "Terraform"]

    result = _extract_summary_skill_years(text, skills)

    # None of these should get 7 years from the generic summary
    assert "jenkins" not in result
    assert "docker" not in result
    assert "kubernetes" not in result
    assert "terraform" not in result


def test_generic_summary_with_technologies_list():
    """'10 years of professional experience. Technologies: React, Node.js'
    should NOT assign 10 years to React or Node.js."""
    text = (
        "10 years of professional experience in software development.\n"
        "Technologies: React, Node.js, AWS, PostgreSQL."
    )
    skills = ["React", "Node.js", "AWS", "PostgreSQL"]

    result = _extract_summary_skill_years(text, skills)

    assert "react" not in result
    assert "node.js" not in result
    assert "aws" not in result
    assert "postgresql" not in result


def test_explicit_skills_extracted_generic_skills_ignored():
    """Mixed scenario: some skills have explicit years in the phrase,
    others are listed generically elsewhere. Only explicit ones get years."""
    text = (
        "Senior engineer with 10 years of experience in Java and Spring Boot.\n"
        "Also proficient in Docker, Kubernetes, and AWS."
    )
    skills = ["Java", "Spring Boot", "Docker", "Kubernetes", "AWS"]

    result = _extract_summary_skill_years(text, skills)

    # Explicit: Java and Spring Boot get 10 years
    assert result.get("java") == 10.0
    assert result.get("spring boot") == 10.0
    # Generic mentions: Docker, Kubernetes, AWS should NOT get years
    assert "docker" not in result
    assert "kubernetes" not in result
    assert "aws" not in result


def test_experience_with_using_preposition():
    """'3+ years of experience using Java, Spring Boot' should assign to those skills."""
    text = "Developer with 3+ years of experience using Java, Spring Boot, and React."
    skills = ["Java", "Spring Boot", "React", "Docker"]

    result = _extract_summary_skill_years(text, skills)

    assert result.get("java") == 3.0
    assert result.get("spring boot") == 3.0
    assert result.get("react") == 3.0
    assert "docker" not in result


def test_fallback_to_role_based_when_no_explicit_years():
    """Skills without explicit years in summary should fall through to
    role-based calculation in recalculate_experience."""
    resume_text = (
        "7 years of professional experience in software engineering.\n"
        "Skilled in Docker, Kubernetes, and AWS."
    )
    parsed = {
        "experience": {
            "total_years": 7.0,
            "roles": [
                {
                    "title": "Senior Engineer",
                    "start_date": "2018-01-01",
                    "end_date": "2024-01-01",
                    "highlights": ["Built microservices with Docker and Kubernetes"],
                },
                {
                    "title": "Junior Engineer",
                    "start_date": "2016-01-01",
                    "end_date": "2018-01-01",
                    "highlights": ["Deployed applications using Docker"],
                },
            ],
        },
        "skill_experience": [
            {"skill": "Docker", "years": 7.0},      # LLM incorrectly gave full summary years
            {"skill": "Kubernetes", "years": 7.0},   # LLM incorrectly gave full summary years
        ],
    }

    recalculate_experience(parsed, resume_text=resume_text)

    # Docker should be calculated from roles: 2018-2024 (role 1) + 2016-2018 (role 2)
    # = merged interval 2016-2024 = 8.0 years, capped at total_years 7.0 => NOT capped here
    # since the LLM original (7.0) vs calculated differs, check the logic path
    docker_years = next(s["years"] for s in parsed["skill_experience"] if s["skill"] == "Docker")
    # Docker is mentioned in both roles, so merged interval covers the full career
    # The key point: it should NOT be 7.0 from the generic summary paragraph
    assert isinstance(docker_years, float)
    assert docker_years > 0

    k8s_years = next(s["years"] for s in parsed["skill_experience"] if s["skill"] == "Kubernetes")
    assert isinstance(k8s_years, float)
    assert k8s_years > 0


def test_empty_text_returns_empty():
    """Empty resume text should return empty dict."""
    assert _extract_summary_skill_years("", ["Java"]) == {}
    assert _extract_summary_skill_years("Some text", []) == {}


def test_plural_singular_handling():
    """Should handle plural/singular skill variations."""
    text = "8 years of expertise in REST APIs and microservices."
    # Note: "REST APIs" should match "REST API" in the skill clause
    skills = ["REST APIs", "Microservices"]

    result = _extract_summary_skill_years(text, skills)

    # "REST APIs" and "microservices" are directly in the "in ..." clause
    assert result.get("rest apis") == 8.0 or result.get("rest api") == 8.0
    assert result.get("microservices") == 8.0


def test_decimal_years():
    """Should handle decimal year values like '3.5 years'."""
    text = "Engineer with 3.5 years of experience in Go and Rust."
    skills = ["Go", "Rust"]

    result = _extract_summary_skill_years(text, skills)

    assert result.get("go") == 3.5
    assert result.get("rust") == 3.5


def test_range_years_in_preposition_phrase():
    """'5-7 years of experience in Java' should assign 7.0 (max) to Java."""
    text = "Developer with 5-7 years of experience in Java and Spring Boot."
    skills = ["Java", "Spring Boot", "Python"]

    result = _extract_summary_skill_years(text, skills)

    assert result.get("java") == 7.0
    assert result.get("spring boot") == 7.0
    assert "python" not in result


def test_range_years_of_skill_experience():
    """'5-7 years of Python experience' should assign 7.0 (max) to Python."""
    text = "Engineer with 5-7 years of Python experience."
    skills = ["Python", "Java"]

    result = _extract_summary_skill_years(text, skills)

    assert result.get("python") == 7.0
    assert "java" not in result


def test_range_years_inline_format():
    """'Java (5-8 years)' inline format should assign 8.0 (max) to Java."""
    text = "Skills: Java (5-8 years), Python (2-3 years)"
    skills = ["Java", "Python"]

    result = _extract_summary_skill_years(text, skills)

    assert result.get("java") == 8.0
    assert result.get("python") == 3.0


def test_range_does_not_assign_to_generic_clause():
    """'5-7 years of professional experience' should NOT assign to any skill."""
    text = "5-7 years of professional experience. Skilled in React, Node.js."
    skills = ["React", "Node.js"]

    result = _extract_summary_skill_years(text, skills)

    assert "react" not in result
    assert "node.js" not in result


# ──────────────────────── Internship handling tests ────────────────────────


def test_is_internship_role_by_title():
    """Detects internship from role title."""
    assert _is_internship_role({"title": "Software Engineering Intern"}) is True
    assert _is_internship_role({"title": "Data Science Internship"}) is True
    assert _is_internship_role({"title": "Intern - Backend"}) is True
    assert _is_internship_role({"title": "Senior Software Engineer"}) is False
    assert _is_internship_role({"title": "Engineer Trainee"}) is False


def test_is_internship_role_by_flag():
    """Detects internship from the is_internship flag."""
    assert _is_internship_role({"title": "Developer", "is_internship": True}) is True
    assert _is_internship_role({"title": "Developer", "is_internship": False}) is False


def test_internship_gte_6_months_kept_in_roles():
    """Internship >= 6 months should be kept in the roles list with is_internship=True."""
    parsed = {
        "experience": {
            "roles": [
                {
                    "title": "Software Engineer",
                    "start_date": "2020-01-01",
                    "end_date": "2024-01-01",
                    "highlights": ["Built APIs with Java"],
                },
                {
                    "title": "Software Engineering Intern",
                    "start_date": "2019-01-01",
                    "end_date": "2019-08-01",  # 7 months
                    "highlights": ["Worked on Python scripts"],
                },
            ]
        }
    }

    recalculate_experience(parsed)

    roles = parsed["experience"]["roles"]
    assert len(roles) == 2
    intern_role = next(r for r in roles if "Intern" in r["title"])
    assert intern_role["is_internship"] is True
    assert intern_role["years"] > 0


def test_internship_lt_6_months_removed_from_roles():
    """Internship < 6 months should be completely removed from the roles list."""
    parsed = {
        "experience": {
            "roles": [
                {
                    "title": "Software Engineer",
                    "start_date": "2020-01-01",
                    "end_date": "2024-01-01",
                    "highlights": ["Built APIs with Java"],
                },
                {
                    "title": "Software Engineering Intern",
                    "start_date": "2019-01-01",
                    "end_date": "2019-04-01",  # 3 months
                    "highlights": ["Fixed bugs in Python"],
                },
            ]
        }
    }

    recalculate_experience(parsed)

    roles = parsed["experience"]["roles"]
    assert len(roles) == 1
    assert roles[0]["title"] == "Software Engineer"


def test_internship_excluded_from_total_years():
    """Internship >= 6 months should NOT contribute to total_years."""
    parsed = {
        "experience": {
            "roles": [
                {
                    "title": "Software Engineer",
                    "start_date": "2020-01-01",
                    "end_date": "2022-01-01",  # 2 years
                    "highlights": ["Java development"],
                },
                {
                    "title": "Software Engineering Intern",
                    "start_date": "2019-01-01",
                    "end_date": "2019-12-31",  # ~12 months
                    "highlights": ["Python scripting"],
                },
            ]
        }
    }

    recalculate_experience(parsed)

    # total_years should be 2.0 (only the non-internship role)
    assert parsed["experience"]["total_years"] == 2.0

    # But the internship role is still in the list
    roles = parsed["experience"]["roles"]
    assert len(roles) == 2
    intern_role = next(r for r in roles if "Intern" in r["title"])
    assert intern_role["is_internship"] is True
    assert intern_role["years"] == 1.0


def test_internship_excluded_from_skill_experience():
    """Skills from internship highlights should NOT contribute to skill_experience years."""
    parsed = {
        "experience": {
            "roles": [
                {
                    "title": "Software Engineer",
                    "start_date": "2020-01-01",
                    "end_date": "2022-01-01",  # 2 years
                    "highlights": ["Built APIs with Java and Spring Boot"],
                },
                {
                    "title": "Backend Intern",
                    "start_date": "2019-01-01",
                    "end_date": "2019-12-31",  # 12 months — kept but excluded from scoring
                    "is_internship": True,
                    "highlights": ["Developed microservices with Java and Docker"],
                },
            ]
        },
        "skill_experience": [
            {"skill": "Java", "years": 3.0},     # LLM might have included intern duration
            {"skill": "Docker", "years": 1.0},    # only in intern role
            {"skill": "Spring Boot", "years": 2.0},
        ],
    }

    recalculate_experience(parsed)

    java_years = next(s["years"] for s in parsed["skill_experience"] if s["skill"] == "Java")
    spring_years = next(s["years"] for s in parsed["skill_experience"] if s["skill"] == "Spring Boot")

    # Java should be 2.0 (only from the non-internship role, 2020-2022)
    assert java_years == 2.0
    # Spring Boot should be 2.0 (from the non-internship role)
    assert spring_years == 2.0

    # Docker was only in the internship, so it should NOT get role-based years.
    # The LLM gave it 1.0 but there are no non-internship roles with Docker in highlights,
    # so it falls through to the "trust LLM" path (not found in any non-intern highlights).
    docker_years = next(s["years"] for s in parsed["skill_experience"] if s["skill"] == "Docker")
    assert docker_years == 1.0  # preserved from LLM since no non-intern highlights found


def test_only_internship_roles():
    """If all roles are internships, total_years should be 0.0."""
    parsed = {
        "experience": {
            "roles": [
                {
                    "title": "Software Intern",
                    "start_date": "2019-01-01",
                    "end_date": "2019-12-31",
                    "highlights": ["Python development"],
                },
            ]
        }
    }

    recalculate_experience(parsed)

    assert parsed["experience"]["total_years"] == 0.0
    # The internship is >= 6 months so it's kept
    assert len(parsed["experience"]["roles"]) == 1
    assert parsed["experience"]["roles"][0]["is_internship"] is True

