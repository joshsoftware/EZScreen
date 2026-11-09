from src.screening_pipeline.summary_calculator import compute_final_summary


def test_compute_final_summary_empty():
    assert compute_final_summary([]) is None


def test_compute_final_summary_shortlists_high_scores():
    evaluations = [
        {"category": "must_have_matched", "score": 8, "follow_ups": []},
        {"category": "must_have_matched", "score": 9, "follow_ups": [{"score": 7}]},
    ]
    result = compute_final_summary(evaluations)

    # Only Must-have was asked, so the other weights move onto it: average 8 → 8.0/10.
    assert result["max_possible_score"] == 100.0
    assert result["overall_score"] == 8.0
    assert result["final_recommendation"] == "shortlist_for_l1"


def test_compute_final_summary_rejects_low_scores():
    evaluations = [
        {"category": "must_have_matched", "score": 2, "follow_ups": []},
        {"category": "experience_domain", "score": 3, "follow_ups": []},
    ]
    result = compute_final_summary(evaluations)

    assert result["final_recommendation"] == "reject"


def test_compute_final_summary_counts_only_persisted_questions_and_zero_scores():
    evaluations = [
        {"question_id": 1, "category": "must_have_matched", "score": 2, "follow_ups": [{"score": 6}]},
        {"question_id": 2, "category": "must_have_matched", "score": 4, "follow_ups": [{"score": 2}]},
        {"question_id": 3, "category": "must_have_matched", "score": 0, "follow_ups": []},
        {"question_id": 4, "category": "experience_domain", "score": 0, "follow_ups": [{"score": 7}]},
        {"question_id": 5, "category": "experience_domain", "score": 2, "follow_ups": [{"score": 6}]},
        {"question_id": 6, "category": "good_to_have", "score": 0, "follow_ups": []},
        {"question_id": 7, "category": "good_to_have", "score": 4, "follow_ups": [{"score": 6}]},
        {"question_id": 8, "category": "good_to_have", "score": 0, "follow_ups": []},
        {"question_id": 9, "category": "lacking_skill", "score": 0, "follow_ups": []},
        {"question_id": 10, "category": "lacking_skill", "score": 6, "follow_ups": []},
        {"question_id": 11, "category": "lacking_skill", "score": 0, "follow_ups": []},
        # Question 12 was not persisted and therefore is intentionally absent.
        {"question_id": 13, "category": "lacking_skill", "score": 0, "follow_ups": []},
        {"question_id": 14, "category": "lacking_skill", "score": 0, "follow_ups": []},
        {"question_id": 15, "category": "lacking_skill", "score": 0, "follow_ups": []},
    ]

    result = compute_final_summary(evaluations)

    # Must-have avg 2.3 × 60, Domain 3.75 × 20, Good to have 1.7 × 10, Skill gaps 1.0 × 10.
    assert result == {
        "total_score": 24.2,
        "max_possible_score": 100.0,
        "overall_score": 2.4,
        "final_recommendation": "reject",
    }
