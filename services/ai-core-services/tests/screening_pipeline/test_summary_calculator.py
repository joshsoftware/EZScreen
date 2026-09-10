from src.screening_pipeline.summary_calculator import compute_final_summary


def test_compute_final_summary_empty():
    assert compute_final_summary([]) is None


def test_compute_final_summary_shortlists_high_scores():
    evaluations = [
        {"score": 8, "follow_ups": []},
        {"score": 9, "follow_ups": [{"score": 7}]},
    ]
    result = compute_final_summary(evaluations)

    assert result["max_possible_score"] == 20
    assert result["overall_score"] >= 6.0
    assert result["final_recommendation"] == "shortlist_for_l1"


def test_compute_final_summary_rejects_low_scores():
    evaluations = [
        {"score": 2, "follow_ups": []},
        {"score": 3, "follow_ups": []},
    ]
    result = compute_final_summary(evaluations)

    assert result["final_recommendation"] == "reject"


def test_compute_final_summary_counts_only_persisted_questions_and_zero_scores():
    evaluations = [
        {"question_id": 1, "score": 2, "follow_ups": [{"score": 6}]},
        {"question_id": 2, "score": 4, "follow_ups": [{"score": 2}]},
        {"question_id": 3, "score": 0, "follow_ups": []},
        {"question_id": 4, "score": 0, "follow_ups": [{"score": 7}]},
        {"question_id": 5, "score": 2, "follow_ups": [{"score": 6}]},
        {"question_id": 6, "score": 0, "follow_ups": []},
        {"question_id": 7, "score": 4, "follow_ups": [{"score": 6}]},
        {"question_id": 8, "score": 0, "follow_ups": []},
        {"question_id": 9, "score": 0, "follow_ups": []},
        {"question_id": 10, "score": 6, "follow_ups": []},
        {"question_id": 11, "score": 0, "follow_ups": []},
        # Question 12 was not persisted and therefore is intentionally absent.
        {"question_id": 13, "score": 0, "follow_ups": []},
        {"question_id": 14, "score": 0, "follow_ups": []},
        {"question_id": 15, "score": 0, "follow_ups": []},
    ]

    result = compute_final_summary(evaluations)

    assert result == {
        "total_score": 25.5,
        "max_possible_score": 140,
        "overall_score": 1.8,
        "final_recommendation": "reject",
    }
