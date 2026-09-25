from src.screening_pipeline.evaluation_builders import (
    build_evaluation_block,
    build_qa_entry,
    build_skip_evaluation,
)
from src.screening_pipeline.prompt_builder import screening_prompt_builder
from src.screening_pipeline.prompts import FOLLOW_UP_SCORE_THRESHOLD, UNIFIED_SCREENING_SYSTEM
from src.screening_pipeline.speech_filter import is_probable_hallucination


def test_build_skip_evaluation():
    question = {
        "id": 1,
        "question": "What is Docker?",
        "expected_keywords": ["container", "image"],
    }
    result = build_skip_evaluation(question, "I don't know", question_number=1)

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
        question,
        "What is Docker?",
        "It runs containers",
        question_number=2,
        follow_ups=follow_ups,
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
        question,
        "What is Docker?",
        "Images and containers",
        primary,
        current,
        question_number=3,
        follow_ups=follow_ups,
    )

    assert result["score"] == 4
    assert result["follow_ups"][0]["score"] == 8


def test_build_unified_prompt_includes_question_and_transcript():
    prompt = screening_prompt_builder.build_unified_prompt(
        current_question="What is Python?",
        transcript="It is a language",
        expected_keywords="Python, interpreted",
        answer_depth="partial_depth",
    )
    assert "What is Python?" in prompt
    assert "It is a language" in prompt
    assert "Python, interpreted" in prompt
    assert "partial_depth" in prompt


def test_build_unified_prompt_marks_follow_up():
    prompt = screening_prompt_builder.build_unified_prompt(
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


def test_unified_system_uses_equal_keyword_and_quality_weights():
    assert "MANDATORY 50/50 SPLIT" in UNIFIED_SCREENING_SYSTEM
    assert "Each component contributes exactly 50%" in UNIFIED_SCREENING_SYSTEM
    assert "round((keyword_match_score + answer_quality_score) / 2)" in UNIFIED_SCREENING_SYSTEM
    assert "Strictness changes only the ANSWER QUALITY SCORE" in UNIFIED_SCREENING_SYSTEM
    assert '"answer_quality_score"' in UNIFIED_SCREENING_SYSTEM
    assert '"keyword_match_score"' in UNIFIED_SCREENING_SYSTEM
    assert '"keywords_found"' in UNIFIED_SCREENING_SYSTEM
    assert '"keywords_missing"' in UNIFIED_SCREENING_SYSTEM
    assert "KEYWORD MATCHING RULES" in UNIFIED_SCREENING_SYSTEM
    assert "deterministically" not in UNIFIED_SCREENING_SYSTEM
    assert '"aware": Score 10 when the answer shows initial/basic' in UNIFIED_SCREENING_SYSTEM
    assert '"partial_depth": Score 6-7 when the answer shows initial/basic' in UNIFIED_SCREENING_SYSTEM
    assert '"full_depth": Score 3-4 when the answer shows only initial/basic' in UNIFIED_SCREENING_SYSTEM


def test_unified_system_decision_threshold_matches_evaluator_constant():
    assert FOLLOW_UP_SCORE_THRESHOLD == 4
    assert f'"NEXT_QUESTION" if the balanced final score >= {FOLLOW_UP_SCORE_THRESHOLD}' in UNIFIED_SCREENING_SYSTEM
    assert f'"ASK_FOLLOW_UP" if the balanced final score < {FOLLOW_UP_SCORE_THRESHOLD}' in UNIFIED_SCREENING_SYSTEM


def test_unified_system_classifies_intent_before_gating_evaluation():
    assert "STEP 1" in UNIFIED_SCREENING_SYSTEM
    assert "ANSWERING" in UNIFIED_SCREENING_SYSTEM
    assert "CLARIFICATION" in UNIFIED_SCREENING_SYSTEM
    assert "SMALL_TALK" in UNIFIED_SCREENING_SYSTEM
    assert "SKIP" in UNIFIED_SCREENING_SYSTEM
    assert "only if intent is ANSWERING" in UNIFIED_SCREENING_SYSTEM
    assert '"intent": "ANSWERING | CLARIFICATION | SMALL_TALK | SKIP"' in UNIFIED_SCREENING_SYSTEM


def test_is_probable_hallucination_filters_noise():
    assert is_probable_hallucination("thank you") is True
    assert is_probable_hallucination("Thanks for watching!") is True
    assert is_probable_hallucination("a") is True
    assert is_probable_hallucination("Docker isolates processes in containers") is False
