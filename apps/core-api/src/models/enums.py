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
    scored = "scored"
    interview_scheduled = "interview_scheduled"
    interview_completed = "interview_completed"
    shortlisted_l2 = "shortlisted_l2"
    rejected = "rejected"


class InterviewType(str, enum.Enum):
    screening_ai = "screening_ai"


class InterviewStatus(str, enum.Enum):
    scheduled = "scheduled"
    rescheduled = "rescheduled"
    completed = "completed"
    no_show = "no_show"
    cancelled = "cancelled"
    failed = "failed"
