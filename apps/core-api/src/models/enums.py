import enum


class UserRole(str, enum.Enum):
    super_admin = "super_admin"
    organization_admin = "organization_admin"
    hr = "hr"
    candidate = "candidate"


class UserStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"
    suspended = "suspended"


class JobStatus(str, enum.Enum):
    draft = "draft"
    published = "published"
    closed = "closed"


class JobType(str, enum.Enum):
    part_time = "part_time"
    full_time = "full_time"
    contract = "contract"


class WorkType(str, enum.Enum):
    onsite = "onsite"
    hybrid = "hybrid"
    remote = "remote"


class ApplicationStatus(str, enum.Enum):
    applied = "applied"
    interview_scheduled = "interview_scheduled"
    interview_completed = "interview_completed"
    shortlist_for_l1 = "shortlist_for_l1"
    rejected = "rejected"


class ApplicationSource(str, enum.Enum):
    hr_bulk = "hr_bulk"
    candidate = "candidate"


class TimelineEventType(str, enum.Enum):
    applied = "applied"
    scored = "scored"
    resume_parsed = "resume_parsed"
    job_fit = "job_fit"
    under_hr_review = "under_hr_review"
    screening_scheduled = "screening_scheduled"
    invite_sent = "invite_sent"
    screening_in_progress = "screening_in_progress"
    screening_completed = "screening_completed"
    analysis_ready = "analysis_ready"
    shortlisted_for_l1 = "shortlisted_for_l1"
    rejected = "rejected"
    screening_rescheduled = "screening_rescheduled"
    screening_no_show = "screening_no_show"
    screening_cancelled = "screening_cancelled"
    screening_failed = "screening_failed"


class TimelineActorType(str, enum.Enum):
    user = "user"
    system = "system"


class InterviewType(str, enum.Enum):
    screening_ai = "screening_ai"


class InterviewStatus(str, enum.Enum):
    scheduled = "scheduled"
    rescheduled = "rescheduled"
    completed = "completed"
    no_show = "no_show"
    cancelled = "cancelled"
    failed = "failed"
