from src.screening_pipeline.session_api import normalize_interview_metadata


def test_normalize_interview_metadata_matches_core_api_transcript_contract():
    payload = normalize_interview_metadata(
        [
            {
                "interaction_type": "question",
                "question_id": 1,
                "bot_speech": "What is Docker?",
                "candidate_answer": "It packages applications.",
                "follow_ups": [
                    {
                        "ai_response": "Can you explain containers?",
                        "candidate_speech": "They isolate processes.",
                    }
                ],
                "conversational_turns": [
                    {"candidate_speech": "Please repeat.", "ai_response": "Certainly."}
                ],
                "silence_prompts": [
                    {"bot_speech": "Are you there?", "candidate_reply": "Yes."}
                ],
            },
            {
                "interaction_type": "closing",
                "bot_speech": "Thank you for your time.",
                "candidate_answer": "",
            },
        ]
    )

    assert payload == [
        {
            "interaction_type": "question",
            "question_id": 1,
            "bot_speech": "What is Docker?",
            "candidate_answer": "It packages applications.",
            "follow_ups": [
                {
                    "interaction_type": "follow_up",
                    "bot_speech": "Can you explain containers?",
                    "candidate_answer": "They isolate processes.",
                }
            ],
        },
        {
            "interaction_type": "conversational",
            "bot_speech": "Certainly.",
            "candidate_answer": "Please repeat.",
            "follow_ups": [],
        },
        {
            "interaction_type": "silence_prompt",
            "bot_speech": "Are you there?",
            "candidate_answer": "Yes.",
            "follow_ups": [],
        },
        {
            "interaction_type": "closing",
            "bot_speech": "Thank you for your time.",
            "candidate_answer": "",
            "follow_ups": [],
        },
    ]
