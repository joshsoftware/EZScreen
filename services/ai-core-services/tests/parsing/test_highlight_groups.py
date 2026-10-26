from src.parsing.resume_parser import normalize_highlights


def _role(**fields):
    return {"experience": {"roles": [fields]}}


def test_groups_keep_headings_and_rebuild_flat_highlights():
    """Bug-036: sub-headings inside a role were flattened away."""
    parsed = _role(
        highlight_groups=[
            {"heading": "Finance Microservices System", "highlights": ["Built a finance module.", "Wrote unit tests."]},
            {"heading": " Microservices Infrastructure & DevOps ", "highlights": ["Implemented CI/CD pipelines."]},
        ]
    )
    normalize_highlights(parsed)
    role = parsed["experience"]["roles"][0]

    assert [g["heading"] for g in role["highlight_groups"]] == [
        "Finance Microservices System",
        "Microservices Infrastructure & DevOps",
    ]
    # Skill-years, job fit and question generation read the flat list.
    assert role["highlights"] == ["Built a finance module.", "Wrote unit tests.", "Implemented CI/CD pipelines."]


def test_old_flat_answer_becomes_one_untitled_group():
    parsed = _role(highlights=["Built APIs.", "  ", "Led a team."])
    normalize_highlights(parsed)
    role = parsed["experience"]["roles"][0]

    assert role["highlight_groups"] == [{"heading": None, "highlights": ["Built APIs.", "Led a team."]}]
    assert role["highlights"] == ["Built APIs.", "Led a team."]


def test_role_without_bullets_has_empty_lists():
    parsed = _role(highlight_groups=[{"heading": None, "highlights": []}])
    normalize_highlights(parsed)
    role = parsed["experience"]["roles"][0]

    assert role["highlight_groups"] == []
    assert role["highlights"] == []


def test_projects_are_cleaned():
    parsed = {
        "experience": {"roles": []},
        "projects": [
            {"name": "E-KYC — Digital Identity Verification Platform", "tech_stack": "Java 17", "highlights": ["Built 4+ services."]},
            {"name": "", "highlights": []},
            "junk",
        ],
    }
    normalize_highlights(parsed)

    assert parsed["projects"] == [
        {
            "name": "E-KYC — Digital Identity Verification Platform",
            "tech_stack": ["Java 17"],
            "highlights": ["Built 4+ services."],
        }
    ]


def test_missing_projects_and_experience_are_tolerated():
    parsed = {}
    normalize_highlights(parsed)
    assert parsed["projects"] == []
