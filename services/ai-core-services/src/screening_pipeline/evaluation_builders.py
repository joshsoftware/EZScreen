"""Pure builders for screening evaluation / Q&A payloads (no I/O)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def build_skip_evaluation(question_obj: Dict, transcript: str) -> Dict[str, Any]:
    """Build a 0-score evaluation for skipped questions."""
    return {
        "question_id": question_obj.get("id"),
        "question": question_obj.get("question", ""),
        "candidate_answer": transcript,
        "score": 0,
        "coverage_percent": 0,
        "keywords_found": [],
        "keywords_missing": question_obj.get("expected_keywords", []),
        "decision": "NEXT_QUESTION",
        "feedback": "Candidate chose to skip this question.",
    }


def build_evaluation_block(
    question_obj: Dict,
    current_q: str,
    transcript: str,
    primary_eval: Optional[Dict],
    current_eval: Dict,
    follow_ups: Optional[List[Dict]] = None,
) -> Dict[str, Any]:
    """Build the final evaluation block for analysis_result.evaluations[]."""
    source = primary_eval if primary_eval else current_eval

    evaluation = {
        "question_id": question_obj.get("id"),
        "question": current_q,
        "candidate_answer": transcript,
        "score": source.get("score", 0),
        "coverage_percent": source.get("coverage_percent", 0),
        "keywords_found": source.get("keywords_found", []),
        "keywords_missing": source.get("keywords_missing", []),
        "decision": source.get("decision", "NEXT_QUESTION"),
        "feedback": source.get("feedback", ""),
    }

    if follow_ups:
        follow_up_data = []
        for fu in follow_ups:
            follow_up_data.append(
                {
                    "follow_up_question": fu.get("ai_response", ""),
                    "follow_up_answer": fu.get("candidate_speech", ""),
                    "score": current_eval.get("score", 0),
                    "coverage_percent": current_eval.get("coverage_percent", 0),
                    "keywords_found": current_eval.get("keywords_found", []),
                    "keywords_missing": current_eval.get("keywords_missing", []),
                    "decision": current_eval.get("decision", "NEXT_QUESTION"),
                    "feedback": current_eval.get("feedback", ""),
                }
            )
        evaluation["follow_ups"] = follow_up_data

    return evaluation


def build_qa_entry(
    question_obj: Dict,
    current_q: str,
    transcript: str,
    follow_ups: Optional[List[Dict]] = None,
) -> Dict[str, Any]:
    """Build the clean Q&A entry for question_answer column."""
    qa_entry = {
        "question_id": question_obj.get("id"),
        "bot_speech": current_q,
        "candidate_answer": transcript,
    }

    if follow_ups:
        qa_follow_ups = []
        for fu in follow_ups:
            qa_follow_ups.append(
                {
                    "bot_speech": fu.get("ai_response", ""),
                    "candidate_answer": fu.get("candidate_speech", ""),
                }
            )
        qa_entry["follow_ups"] = qa_follow_ups

    return qa_entry
