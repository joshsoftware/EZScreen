import pytest

from src.question_generation.question_parsing import parse_questions


def test_parse_questions_from_list():
    questions = parse_questions(
        [
            {
                "id": 1,
                "category": "must_have_matched",
                "skill_focus": "Python",
                "question": "Explain GIL?",
                "expected_keywords": ["threads", "lock"],
                "answer_depth": "partial_depth",
            }
        ]
    )

    assert len(questions) == 1
    assert questions[0].skill_focus == "Python"


def test_parse_questions_from_wrapped_dict():
    questions = parse_questions(
        {
            "questions": [
                {
                    "id": 2,
                    "category": "lacking_skill",
                    "skill_focus": "Docker",
                    "question": "What is a container?",
                    "expected_keywords": ["isolation"],
                    "answer_depth": "aware",
                }
            ]
        }
    )

    assert questions[0].id == 2


def test_parse_questions_rejects_non_list():
    with pytest.raises(ValueError, match="Expected JSON array"):
        parse_questions({"nope": True})
