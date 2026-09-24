from pydantic import BaseModel, Field, field_validator
from typing import List, Optional

class ParseResumeRequest(BaseModel):
    resume_name: str = Field(..., description="Name of the resume file")
    resume_path: str = Field(..., description="Path to the resume PDF in the storage bucket")

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

class CandidateSkillExperience(BaseModel):
    skill: str
    years: Optional[float] = None

class ParsedResumeData(BaseModel):
    personal_info: Optional[PersonalInfo] = None
    primary_skills: List[str] = Field(default_factory=list)
    secondary_skills: List[str] = Field(default_factory=list)
    domain_expertise: List[str] = Field(default_factory=list)
    experience: Experience = Field(default_factory=Experience)
    skill_experience: List[CandidateSkillExperience] = Field(default_factory=list)
    education_certificates: List[EducationCertificate] = Field(default_factory=list)

class ParsedResumeResponse(BaseModel):
    resume_name: str
    status: str
    parsed_resume: Optional[ParsedResumeData] = None
    error_message: Optional[str] = None

# --- Job Description (JD) Schemas ---

class RawJDRequest(BaseModel):
    # Accept any extra fields
    model_config = {"extra": "allow"}


class ExperienceRequired(BaseModel):
    min_years: Optional[float] = None
    max_years: Optional[float] = None

class SkillRequirement(BaseModel):
    skill: str
    required_years: Optional[float] = None

class JDSkills(BaseModel):
    must_have: List[SkillRequirement] = Field(default_factory=list)
    good_to_have: List[SkillRequirement] = Field(default_factory=list)

class ParsedJDData(BaseModel):
    title: Optional[str] = None
    company: Optional[str] = None
    company_description: Optional[str] = None
    experience_required: ExperienceRequired = Field(default_factory=ExperienceRequired)
    skills: JDSkills = Field(default_factory=JDSkills)
    qualifications: List[str] = Field(default_factory=list)
    responsibilities: List[str] = Field(default_factory=list)
    location: Optional[str] = None
    employment_type: Optional[str] = None

class ParsedJDResponse(BaseModel):
    status: str
    parsed_jd: Optional[ParsedJDData] = None
    error_message: Optional[str] = None


class NeedsReviewItem(BaseModel):
    label: str = "Other"
    content: str = ""


def _coerce_str_list(value: object) -> object:
    if value is None:
        return []
    if isinstance(value, str):
        lines = [line.strip() for line in value.replace("\r\n", "\n").split("\n")]
        return [line for line in lines if line]
    return value


class JDFormPrefillData(BaseModel):
    title: Optional[str] = None
    location: Optional[str] = None
    job_type: Optional[str] = None
    work_type: Optional[str] = None
    experience_min: Optional[float] = None
    experience_max: Optional[float] = None
    role_summary: Optional[str] = None
    about_company: Optional[str] = None
    responsibilities: List[str] = Field(default_factory=list)
    must_have_skills_text: List[str] = Field(default_factory=list)
    good_to_have_skills_text: List[str] = Field(default_factory=list)
    qualifications: List[str] = Field(default_factory=list)
    domain_experience: List[str] = Field(default_factory=list)
    tools_stack: List[str] = Field(default_factory=list)
    needs_review: List[NeedsReviewItem] = Field(default_factory=list)

    @field_validator(
        "responsibilities",
        "must_have_skills_text",
        "good_to_have_skills_text",
        "qualifications",
        "domain_experience",
        "tools_stack",
        mode="before",
    )
    @classmethod
    def coerce_lists(cls, value: object) -> object:
        return _coerce_str_list(value)

    @field_validator("needs_review", mode="before")
    @classmethod
    def coerce_needs_review(cls, value: object) -> object:
        if value is None:
            return []
        if isinstance(value, str):
            text = value.strip()
            return [{"label": "Other", "content": text}] if text else []
        return value


class JDFormPrefillResponse(BaseModel):
    status: str
    form: Optional[JDFormPrefillData] = None
    error_message: Optional[str] = None
