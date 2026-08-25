from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from src.parsing.schemas import ParsedResumeData, ParsedJDData


class GenerateQuestionsRequest(BaseModel):
    interview_session_id: str = Field(..., description="UUID of the interview session")
    parsed_resume: ParsedResumeData = Field(..., description="Parsed resume JSON from Pipeline B")
    parsed_jd: ParsedJDData = Field(..., description="Parsed JD JSON from Pipeline A")
    job_fit_analysis: Dict[str, Any] = Field(..., description="Full match analysis JSON from the matching endpoint")


class GeneratedQuestion(BaseModel):
    id: int = Field(..., description="Sequential question number (1-15)")
    category: str = Field(..., description="must_have_matched | lacking_skill | good_to_have | experience_domain")
    skill_focus: str = Field(..., description="The specific skill or topic being tested")
    question: str = Field(..., description="The interview question text")
    expected_keywords: List[str] = Field(default_factory=list, description="3 to 5 keywords a correct answer must touch")
    answer_depth: str = Field(..., description="aware | partial_depth | full_depth")


class GenerateQuestionsResponse(BaseModel):
    interview_session_id: str
    status: str = "success"
    questions: Optional[List[GeneratedQuestion]] = None
    count: int = 0
    error_message: Optional[str] = None
