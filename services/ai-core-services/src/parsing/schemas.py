from pydantic import BaseModel, Field
from typing import List, Optional

class ParseResumeRequest(BaseModel):
    application_id: str = Field(..., description="Unique identifier for the application")
    resume_path: str = Field(..., description="Path to the resume PDF in the storage bucket")

class ParseResumeBulkRequest(BaseModel):
    resumes: List[ParseResumeRequest] = Field(..., description="List of resumes to parse")

class PersonalInfo(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None
    email: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    leetcode_url: Optional[str] = None

class EducationCertificate(BaseModel):
    name: str
    issuer: Optional[str] = None
    year: Optional[str] = None
    type: Optional[str] = None

class Role(BaseModel):
    title: Optional[str] = None
    company: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    years: Optional[float] = None
    highlights: List[str] = Field(default_factory=list)

class Experience(BaseModel):
    total_years: Optional[float] = None
    roles: List[Role] = Field(default_factory=list)

class ParsedResumeData(BaseModel):
    personal_info: Optional[PersonalInfo] = None
    primary_skills: List[str] = Field(default_factory=list)
    secondary_skills: List[str] = Field(default_factory=list)
    domain_expertise: List[str] = Field(default_factory=list)
    experience: Experience = Field(default_factory=Experience)
    education_certificates: List[EducationCertificate] = Field(default_factory=list)

class ParsedResumeResponse(BaseModel):
    application_id: str
    status: str
    parsed_resume: Optional[ParsedResumeData] = None
    error_message: Optional[str] = None

# --- Job Description (JD) Schemas ---

class ParseJDRequest(BaseModel):
    job_id: str = Field(..., description="Unique identifier for the job description")
    jd_text: str = Field(..., description="Raw text of the job description")

class ParseJDBulkRequest(BaseModel):
    jds: List[ParseJDRequest] = Field(..., description="List of JDs to parse")

class ParsedJDData(BaseModel):
    job_title: Optional[str] = None
    must_have_skills: List[str] = Field(default_factory=list)
    good_to_have_skills: List[str] = Field(default_factory=list)
    min_experience_years: Optional[float] = None
    max_experience_years: Optional[float] = None
    educational_requirements: List[str] = Field(default_factory=list)

class ParsedJDResponse(BaseModel):
    job_id: str
    status: str
    parsed_jd: Optional[ParsedJDData] = None
    error_message: Optional[str] = None
