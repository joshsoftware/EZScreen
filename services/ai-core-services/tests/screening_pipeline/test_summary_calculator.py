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

    # Each question counts as max(main, follow-up):
    # 6 + 4 + 0 + 7 + 6 + 0 + 6 + 0 + 0 + 6 + 0 + 0 + 0 + 0 = 35 of 140
    assert result == {
        "total_score": 35.0,
        "max_possible_score": 140,
        "overall_score": 2.5,
        "final_recommendation": "reject",
    }


def test_question_counts_as_the_higher_of_main_answer_and_follow_up():
    from src.screening_pipeline.summary_calculator import topic_score

    # A failed follow-up keeps the main answer's score (was averaged to 1.5).
    assert topic_score({"score": 3, "follow_ups": [{"score": 0}]}) == 3.0
    # A good follow-up counts in full (not averaged).
    assert topic_score({"score": 3, "follow_ups": [{"score": 8}]}) == 8.0
    # No follow-up, or an unscored one: the main answer stands.
    assert topic_score({"score": 6}) == 6.0
    assert topic_score({"score": 6, "follow_ups": [{"follow_up_answer": "x"}]}) == 6.0
    # More than one follow-up: the best one counts.
    assert topic_score({"score": 2, "follow_ups": [{"score": 4}, {"score": 8}]}) == 8.0
