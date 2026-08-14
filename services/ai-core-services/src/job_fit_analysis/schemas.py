from pydantic import BaseModel, Field
from typing import List, Optional
from src.parsing.schemas import ParsedResumeData, ParsedJDData

class MatchRequest(BaseModel):
    application_id: str
    job_id: str
    parsed_resume: ParsedResumeData
    parsed_jd: ParsedJDData

class MatchBulkRequest(BaseModel):
    matches: List[MatchRequest] = Field(..., description="List of resumes and JDs to match")

class ScoreBreakdown(BaseModel):
    must_have_skills_score: float
    experience_score: float
    good_to_have_skills_score: float
    qualifications_score: float

class SkillCategorization(BaseModel):
    must_have: List[str] = Field(default_factory=list)
    good_to_have: List[str] = Field(default_factory=list)

class MatchScore(BaseModel):
    score_breakdown: ScoreBreakdown
    match_score: float = Field(..., description="Final match score out of 10.0")
    reasoning: List[str] = Field(..., description="Bullet points explaining the reasoning")
    matched_skills: SkillCategorization
    missing_skills: SkillCategorization
    qualification_match: bool
    experience_match: bool

class MatchResponse(BaseModel):
    application_id: str
    job_id: str
    status: str
    job_fit_analysis: Optional[MatchScore] = None
    error_message: Optional[str] = None
