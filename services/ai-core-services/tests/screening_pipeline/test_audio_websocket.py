from src.screening_pipeline.audio_websocket import _should_forward_candidate_audio


def test_mixed_audio_is_used_as_fallback_only_while_listening_or_closing():
    assert _should_forward_candidate_audio("realtime_audio.mixed", "listening", False)
    assert _should_forward_candidate_audio("realtime_audio.mixed", "closing", False)
    assert not _should_forward_candidate_audio("realtime_audio.mixed", "speaking", False)


def test_user_audio_is_preferred_over_mixed_audio():
    assert _should_forward_candidate_audio("realtime_audio.user", "speaking", False)
    assert not _should_forward_candidate_audio("realtime_audio.mixed", "listening", True)
