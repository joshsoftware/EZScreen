from src.screening_pipeline.evaluation_builders import (
    build_evaluation_block,
    build_qa_entry,
    build_skip_evaluation,
)
from src.screening_pipeline.prompt_builder import screening_prompt_builder
from src.screening_pipeline.speech_filter import is_probable_hallucination


def test_build_skip_evaluation():
    question = {
        "id": 1,
        "question": "What is Docker?",
        "expected_keywords": ["container", "image"],
    }
    result = build_skip_evaluation(question, "I don't know")

    assert result["score"] == 0
    assert result["question_id"] == 1
    assert result["keywords_missing"] == ["container", "image"]
    assert result["decision"] == "NEXT_QUESTION"


def test_build_qa_entry_with_follow_ups():
    question = {"id": 2}
    follow_ups = [
        {"ai_response": "Can you elaborate?", "candidate_speech": "Containers isolate apps"}
    ]
    result = build_qa_entry(
        question, "What is Docker?", "It runs containers", follow_ups
    )

    assert result["bot_speech"] == "What is Docker?"
    assert result["candidate_answer"] == "It runs containers"
    assert len(result["follow_ups"]) == 1
    assert result["follow_ups"][0]["bot_speech"] == "Can you elaborate?"


def test_build_evaluation_block_uses_primary_eval_when_present():
    question = {"id": 3}
    primary = {
        "score": 4,
        "coverage_percent": 30,
        "keywords_found": ["container"],
        "keywords_missing": ["image"],
        "decision": "ASK_FOLLOW_UP",
        "feedback": "Too shallow",
    }
    current = {
        "score": 8,
        "coverage_percent": 80,
        "keywords_found": ["container", "image"],
        "keywords_missing": [],
        "decision": "NEXT_QUESTION",
        "feedback": "Better",
    }
    follow_ups = [
        {"ai_response": "Tell me more", "candidate_speech": "Images and containers"}
    ]

    result = build_evaluation_block(
        question, "What is Docker?", "Images and containers", primary, current, follow_ups
    )

    assert result["score"] == 4
    assert result["follow_ups"][0]["score"] == 8


def test_build_intent_prompt():
    prompt = screening_prompt_builder.build_intent_prompt("What is Python?", "It is a language")
    assert "What is Python?" in prompt
    assert "It is a language" in prompt


def test_build_evaluation_prompt_marks_follow_up():
    prompt = screening_prompt_builder.build_evaluation_prompt(
        current_question="What is Docker?",
        transcript="Containers",
        expected_keywords="container, image",
        answer_depth="partial_depth",
        follow_up_context=[
            {"ai_response": "Say more", "candidate_speech": "boxes"}
        ],
    )
    assert "FOLLOW-UP evaluation" in prompt
    assert "partial_depth" in prompt


def test_is_probable_hallucination_filters_noise():
    assert is_probable_hallucination("thank you") is True
    assert is_probable_hallucination("Thanks for watching!") is True
    assert is_probable_hallucination("a") is True
    assert is_probable_hallucination("Docker isolates processes in containers") is False
