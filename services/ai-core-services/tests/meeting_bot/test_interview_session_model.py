from src.db.models.interview_session import _normalize_interview_metadata


def test_normalize_interview_metadata_parses_legacy_json_string():
    assert _normalize_interview_metadata(
        '{"platform": "attendee", "bot_id": "bot-123"}'
    ) == {"platform": "attendee", "bot_id": "bot-123"}


def test_normalize_interview_metadata_preserves_dictionary():
    metadata = {"bot_id": "bot-123"}

    assert _normalize_interview_metadata(metadata) is metadata


def test_normalize_interview_metadata_ignores_invalid_json_string():
    assert _normalize_interview_metadata("not-json") is None
