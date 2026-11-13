from src.screening_pipeline.candidate_identity import looks_like_bot, name_matches_candidate


def test_display_name_matches_the_candidate_by_first_or_last_name():
    assert name_matches_candidate("Pooja Sharma", "Pooja", "Sharma")
    assert name_matches_candidate("pooja.sharma", "Pooja", "Sharma")
    assert name_matches_candidate("Sharma P", "Pooja", "Sharma")
    assert name_matches_candidate("POOJA", "Pooja", None)
    assert name_matches_candidate("José Pérez", "Jose", "Perez")


def test_other_names_and_initials_do_not_match():
    assert not name_matches_candidate("Rahul Mehta", "Pooja", "Sharma")
    assert not name_matches_candidate("P S", "Pooja", "Sharma")
    assert not name_matches_candidate("Poojan Shah", "Pooja", "Sharma")
    assert not name_matches_candidate("", "Pooja", "Sharma")
    assert not name_matches_candidate("Pooja Sharma", None, None)


def test_note_takers_and_bots_are_recognised():
    for name in [
        "Read.ai meeting notes",
        "Otter.ai",
        "Fireflies.ai Notetaker",
        "Fathom",
        "tl;dv",
        "Pooja's AI Notetaker",
        "Meeting Bot",
        "ezscreener",
    ]:
        assert looks_like_bot(name), name
    for name in ["Pooja Sharma", "Rahul Mehta", "Botha Naidu", "Ottery"]:
        assert not looks_like_bot(name), name
