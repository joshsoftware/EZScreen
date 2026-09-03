"""Interview screening transcript and evaluation schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SuccessMessageResponse(BaseModel):
    success: bool = True
    message: str


class QaFollowUpItem(BaseModel):
    bot_speech: str = Field(..., min_length=1)
    candidate_answer: str = Field(..., min_length=1)


class SaveQaTranscriptRequest(BaseModel):
    question_id: int = Field(..., ge=1)
    bot_speech: str = Field(..., min_length=1)
    candidate_answer: str = Field(..., min_length=1)
    follow_ups: list[QaFollowUpItem] = Field(default_factory=list)


class EvaluationFollowUpItem(BaseModel):
    follow_up_question: str = Field(..., min_length=1)
    follow_up_answer: str = Field(..., min_length=1)
    score: float = Field(..., ge=0, le=10)
    coverage_percent: float = Field(..., ge=0, le=100)
    keywords_found: list[str] = Field(default_factory=list)
    keywords_missing: list[str] = Field(default_factory=list)
    decision: Literal["ASK_FOLLOW_UP", "NEXT_QUESTION"]
    feedback: str = Field(..., min_length=1)


class SaveEvaluationRequest(BaseModel):
    question_id: int = Field(..., ge=1)
    question: str = Field(..., min_length=1)
    candidate_answer: str = Field(..., min_length=1)
    score: float = Field(..., ge=0, le=10)
    coverage_percent: float = Field(..., ge=0, le=100)
    keywords_found: list[str] = Field(default_factory=list)
    keywords_missing: list[str] = Field(default_factory=list)
    decision: Literal["ASK_FOLLOW_UP", "NEXT_QUESTION"]
    feedback: str = Field(..., min_length=1)
    follow_ups: list[EvaluationFollowUpItem] = Field(default_factory=list)


class SaveEvaluationSummaryRequest(BaseModel):
    total_score: float = Field(..., ge=0)
    max_possible_score: float = Field(..., gt=0)
    overall_score: float = Field(..., ge=0, le=10)
    final_recommendation: Literal["shortlist_for_l1", "reject", "review"]


class TranscriptFollowUpItem(BaseModel):
    interaction_type: str = Field(..., min_length=1)
    bot_speech: str = Field(..., min_length=1)
    candidate_answer: str = Field(..., min_length=1)


class TranscriptInteractionItem(BaseModel):
    interaction_type: str = Field(..., min_length=1)
    bot_speech: str = Field(..., min_length=1)
    candidate_answer: str = Field(..., min_length=1)
    question_id: int | None = Field(default=None, ge=1)
    follow_ups: list[TranscriptFollowUpItem] = Field(default_factory=list)


class SaveTranscriptRequest(BaseModel):
    interview_metadata: list[TranscriptInteractionItem] = Field(..., min_length=1)
