from pydantic import BaseModel, Field
from typing import List, Optional
from src.parsing.schemas import ParsedResumeData, ParsedJDData

class MatchRequest(BaseModel):
    application_id: str
    job_id: str
    parsed_resume: ParsedResumeData
    parsed_jd: ParsedJDData

class ScoreBreakdown(BaseModel):
    raw_must_have_skills: float
    raw_good_to_have_skills: float
    raw_experience: float
    raw_qualifications: float
    skills_score: float
    experience_score: float
    qualifications_score: float

class SkillCategorization(BaseModel):
    must_have: List[str] = Field(default_factory=list)
    good_to_have: List[str] = Field(default_factory=list)

class SkillMatchExperience(BaseModel):
    skill: str
    required_years: Optional[float] = None
    candidate_years: Optional[float] = None
    skill_experience_ratio: float
    meets_requirement: bool

class MatchScore(BaseModel):
    score_breakdown: ScoreBreakdown
    match_score: float = Field(..., description="Final match score out of 10.0")
    reasoning: List[str] = Field(..., description="Bullet points explaining the overall reasoning")
    strengths: List[str] = Field(default_factory=list, description="Strengths based on resume vs JD comparison")
    concerns: List[str] = Field(default_factory=list, description="Concerns based on resume vs JD comparison")
    matched_skills: SkillCategorization
    missing_skills: SkillCategorization
    must_have_experience: List[SkillMatchExperience] = Field(default_factory=list)
    good_to_have_experience: List[SkillMatchExperience] = Field(default_factory=list)
    qualification_match: bool
    experience_match: bool

class MatchResponse(BaseModel):
    application_id: str
    job_id: str
    status: str
    job_fit_analysis: Optional[MatchScore] = None
    error_message: Optional[str] = None
