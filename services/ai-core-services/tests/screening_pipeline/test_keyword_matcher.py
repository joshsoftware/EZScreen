from src.screening_pipeline.keyword_matcher import calculate_keyword_coverage


def test_keyword_coverage_matches_whole_words_and_punctuation_variants():
    coverage = calculate_keyword_coverage(
        "I use CI CD pipelines to deploy a Docker container.",
        ["CI/CD", "Docker", "Kubernetes"],
    )

    assert coverage.found == ["CI/CD", "Docker"]
    assert coverage.missing == ["Kubernetes"]
    assert coverage.coverage_percent == 67
    assert coverage.score == 6.7


def test_keyword_coverage_does_not_match_a_keyword_inside_another_word():
    coverage = calculate_keyword_coverage("I have worked with NoSQL databases.", ["SQL"])

    assert coverage.found == []
    assert coverage.missing == ["SQL"]
    assert coverage.coverage_percent == 0


def test_keyword_coverage_accepts_high_confidence_speech_to_text_variation():
    coverage = calculate_keyword_coverage(
        "A copy on right array list iterates over a snapshot.",
        ["CopyOnWriteArrayList"],
    )

    assert coverage.found == ["CopyOnWriteArrayList"]
    assert coverage.coverage_percent == 100


def test_keyword_coverage_accepts_ordered_abbreviated_compound_name():
    coverage = calculate_keyword_coverage(
        "A copyon arraylist iterates over a snapshot.",
        ["CopyOnWriteArrayList"],
    )

    assert coverage.found == ["CopyOnWriteArrayList"]


def test_keyword_coverage_rejects_lower_confidence_phrase_variation():
    coverage = calculate_keyword_coverage(
        "A copy on read array list iterates over a snapshot.",
        ["CopyOnWriteArrayList"],
    )

    assert coverage.found == []
