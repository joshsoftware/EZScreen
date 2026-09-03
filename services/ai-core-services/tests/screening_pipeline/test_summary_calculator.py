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
