from src.parsing.experience_calculator import recalculate_experience


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
