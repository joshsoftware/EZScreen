# EZScreen REST & Inter-Service API Specification

> **Version**: 1.0.0  
> **Base URL**: `https://api.ezscreen.io/api/v1` (Production Core API) / `http://localhost:8000/api/v1` (Local Dev)  
> **Internal Service Base URL**: `http://parsing-matching:8001/internal/v1`, `http://ai-screening:8002/internal/v1`  
> **Format**: JSON (`Content-Type: application/json`)  
> **Auth**: Bearer Token (`Authorization: Bearer <jwt>`)

---

## 1. System Roles & Multi-Tenancy Architecture

| Role | Scope | Key Capabilities & Provisioning Rules |
| :--- | :--- | :--- |
| **`super_admin`** | Platform Scope (`organization_id NULL`) | Platform owner. Creates Organizations (`organizations`); provisions `organization_admin` and `hr` users. |
| **`organization_admin`** | Organization Scope (`organization_id NOT NULL`) | Organization Administrator. Bound strictly to one organization. Provisions secondary `organization_admin` and `hr` users within their organization. |
| **`hr`** | Organization Scope (`organization_id NOT NULL`) | Operational HR user. Bound strictly to one organization. Parses & publishes JDs, views applicant scores, schedules AI interview sessions, and reviews screening reports. |
| **`candidate`** | Candidate Scope (`organization_id NULL`) | Guest / Candidate applicant. Browses published jobs via organization subdomain (`{org}.ezscreen.io`) and submits resume applications. |

---

## 2. Modular Architecture & Inter-Service API Boundaries

The API architecture mirrors our **Modular Monolith / Microservices boundary design**:

```
 ┌────────────────────────────────────────────────────────────────────────┐
 │                      React SPA (apps/web-frontend)                     │
 └───────────────────────────────────┬────────────────────────────────────┘
                                     │ External REST / Webhook
                                     ▼
 ┌────────────────────────────────────────────────────────────────────────┐
 │                   Core API Service (apps/core-api)                     │
 └─────────────────┬──────────────────────────────────────┬───────────────┘
                   │                                      │
  Internal REST    │                                      │ Internal REST
  POST /parse/jd   │                                      │ POST /questions/generate
  POST /match      ▼                                      ▼ POST /bot/dispatch & /evaluate
 ┌────────────────────────────────────┐  ┌────────────────────────────────────┐
 │    Parsing & Matching Service      │  │        AI Screening Service        │
 │    (services/parsing-matching)     │  │        (services/ai-screening)      │
 └────────────────────────────────────┘  └────────────────────────────────────┘
```

---

## 3. Core API Service Endpoints (`apps/core-api`)

### A. Authentication & Account Management

#### POST /api/v1/auth/login
**Purpose**: Authenticate Super Admin, Organization Admin, or HR user and return JWT access token.  
**Roles**: Public  

```json
Request:
{
  "email": "admin@acme.com",
  "password": "SecurePassword123!"
}

Response 200:
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "email": "admin@acme.com",
    "first_name": "Alice",
    "last_name": "Admin",
    "role": "organization_admin",
    "status": "active",
    "organization_id": "987e6543-e89b-12d3-a456-426614174000"
  }
}
```

#### POST /api/v1/auth/logout
**Purpose**: Revoke current session token and clear refresh cookie.  
**Roles**: Authenticated  

#### POST /api/v1/auth/forgot-password
**Purpose**: Request a password reset link via email.  
**Roles**: Public  

#### POST /api/v1/auth/reset-password
**Purpose**: Reset password using token received in email.  
**Roles**: Public (valid token required)  

#### GET /api/v1/auth/me
**Purpose**: Retrieve profile of current authenticated user.  
**Roles**: Authenticated  

---

### B. Organization & User Provisioning Endpoints

#### POST /api/v1/organizations
**Purpose**: Super Admin creates a new Organization (`organizations`).  
**Roles**: `super_admin`  

```json
Request:
{
  "name": "Acme Corporation",
  "domain": "acme",
  "logo_url": "https://acme.com/logo.png"
}

Response 201:
{
  "id": "987e6543-e89b-12d3-a456-426614174000",
  "name": "Acme Corporation",
  "domain": "acme",
  "logo_url": "https://acme.com/logo.png",
  "is_active": true,
  "created_at": "2026-08-04T12:00:00Z"
}
```

#### GET /api/v1/organizations
**Purpose**: List all organizations across the platform.  
**Roles**: `super_admin`  

#### GET /api/v1/organizations/{id}
**Purpose**: View details for organization `{id}`.  
**Roles**: `super_admin`, `organization_admin` (own org)  

#### PUT /api/v1/organizations/{id}
**Purpose**: Update organization details (name, domain, logo URL).  
**Roles**: `super_admin`, `organization_admin` (own org)  

#### DELETE /api/v1/organizations/{id}
**Purpose**: Soft delete / deactivate an organization (`is_active = false`).  
**Roles**: `super_admin`  

#### GET /api/v1/organizations/{id}/users
**Purpose**: List all users belonging to organization `{id}`.  
**Roles**: `super_admin`, `organization_admin` (own org)  

#### POST /api/v1/organizations/{id}/users
**Purpose**: Unified provisioning endpoint to create an `organization_admin` or `hr` user for organization `{id}`. Accessible by both `super_admin` and `organization_admin`.  
**Roles**: `super_admin`, `organization_admin` (own org)  

```json
Request:
{
  "email": "hr.jane@acme.com",
  "password": "SecurePassword123!",
  "first_name": "Jane",
  "last_name": "Smith",
  "phone": "+1-555-0199",
  "role": "hr"
}

Response 201:
{
  "id": "333e4567-e89b-12d3-a456-426614174000",
  "organization_id": "987e6543-e89b-12d3-a456-426614174000",
  "role": "hr",
  "email": "hr.jane@acme.com",
  "first_name": "Jane",
  "last_name": "Smith",
  "phone": "+1-555-0199",
  "status": "active",
  "created_at": "2026-08-04T12:10:00Z"
}
```

---

### C. Job Description Endpoints (Direct Parsing, Unified Update)

#### POST /api/v1/jobs/parse
**Purpose**: Direct in-memory parsing of raw JD file (PDF/DOCX) or raw text. Calls `services/parsing-matching` internally and returns extracted `parsed_jd` fields directly to the UI form for HR verification.  
**Roles**: `hr`, `organization_admin`, `super_admin`  

```json
Request (JSON or Multipart Form-Data):
{
  "raw_text": "Senior Java Developer with 3-5 years experience in Spring Boot, PostgreSQL, and Docker."
}

Response 200:
{
  "title": "Senior Java Developer",
  "job_type": "full_time",
  "work_type": "hybrid",
  "location": "Bangalore",
  "experience_min": 3,
  "experience_max": 5,
  "skills": "Java, Spring Boot, PostgreSQL, Docker",
  "parsed_jd": {
    "role": "Senior Java Developer",
    "required_skills": ["Java", "Spring Boot", "PostgreSQL"],
    "preferred_skills": ["Docker", "AWS"],
    "experience": {"min": 3, "max": 5},
    "education": "Bachelor Degree",
    "responsibilities": ["Develop REST APIs", "Optimize DB queries"]
  }
}
```

#### POST /api/v1/jobs
**Purpose**: Save and publish a `job_descriptions` record using HR-verified fields directly into PostgreSQL.  
**Roles**: `hr`, `organization_admin`, `super_admin`  

```json
Request:
{
  "title": "Senior Java Developer",
  "description": "Looking for a Senior Java Developer...",
  "job_type": "full_time",
  "work_type": "hybrid",
  "location": "Bangalore",
  "experience_min": 3,
  "experience_max": 5,
  "skills": "Java, Spring Boot, PostgreSQL, Docker",
  "parsed_jd": {
    "role": "Senior Java Developer",
    "required_skills": ["Java", "Spring Boot", "PostgreSQL"],
    "preferred_skills": ["Docker", "AWS"],
    "experience": {"min": 3, "max": 5},
    "education": "Bachelor Degree",
    "responsibilities": ["Develop REST APIs", "Optimize DB queries"]
  },
  "status": "published"
}

Response 201:
{
  "id": "444e4567-e89b-12d3-a456-426614174000",
  "organization_id": "987e6543-e89b-12d3-a456-426614174000",
  "created_by": "333e4567-e89b-12d3-a456-426614174000",
  "title": "Senior Java Developer",
  "job_type": "full_time",
  "work_type": "hybrid",
  "location": "Bangalore",
  "experience_min": 3,
  "experience_max": 5,
  "skills": "Java, Spring Boot, PostgreSQL, Docker",
  "status": "published",
  "parsed_jd": { ... },
  "published_at": "2026-08-04T12:15:00Z",
  "created_at": "2026-08-04T12:15:00Z"
}
```

#### GET /api/v1/jobs
**Purpose**: List all job descriptions for the authenticated user's organization.  
**Roles**: `hr`, `organization_admin`, `super_admin`  

#### GET /api/v1/jobs/{id}
**Purpose**: Get detailed job description and `parsed_jd` JSONB payload.  
**Roles**: `hr`, `organization_admin`, `super_admin`  

#### PUT /api/v1/jobs/{id}
**Purpose**: Unified endpoint to update job description fields, `parsed_jd` requirements, AND/OR status (`draft`, `published`, `closed`).  
**Roles**: `hr`, `organization_admin`, `super_admin`  

```json
Request:
{
  "title": "Lead Java Backend Engineer",
  "description": "Updated job description text...",
  "status": "closed"
}

Response 200:
{
  "id": "444e4567-e89b-12d3-a456-426614174000",
  "title": "Lead Java Backend Engineer",
  "status": "closed",
  "updated_at": "2026-08-04T19:30:00Z"
}
```

---

### D. Public Candidate Endpoints (Subdomain Scoped)

#### GET /api/v1/public/jobs
**Purpose**: Public candidates view published jobs for an organization resolved via subdomain (`{org}.ezscreen.io`).  
**Roles**: `candidate` (Public)  

#### GET /api/v1/public/jobs/{id}
**Purpose**: View details of a specific published job description.  
**Roles**: `candidate` (Public)  

#### POST /api/v1/public/jobs/{id}/apply
**Purpose**: Candidate submits job application with resume file. Automatically invokes `services/parsing-matching` to parse resume (`parsed_resume`) and calculate matching score (`matching_result`).  
**Roles**: `candidate` (Public)  

```json
Request (Multipart Form-Data):
{
  "email": "john.doe@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "phone": "+1-555-0188",
  "resume": "<file_binary>"
}

Response 201:
{
  "id": "555e4567-e89b-12d3-a456-426614174000",
  "job_description_id": "444e4567-e89b-12d3-a456-426614174000",
  "candidate_id": "777e4567-e89b-12d3-a456-426614174000",
  "status": "applied",
  "resume_score": 85.00,
  "candidate_yoe": 5.0,
  "applied_at": "2026-08-04T12:30:00Z"
}
```

---

### E. Candidate Visibility & Application Management Endpoints

#### GET /api/v1/jobs/{id}/applicants
**Purpose**: List all candidate applications for a job posting sorted by `resume_score` DESC.  
**Roles**: `hr`, `organization_admin`, `super_admin`  

#### GET /api/v1/applications/{id}
**Purpose**: Get full application details, including `parsed_resume` and `matching_result` JSONB schemas.  
**Roles**: `hr`, `organization_admin`, `super_admin`  

```json
Response 200:
{
  "id": "555e4567-e89b-12d3-a456-426614174000",
  "job_description_id": "444e4567-e89b-12d3-a456-426614174000",
  "candidate_id": "777e4567-e89b-12d3-a456-426614174000",
  "status": "applied",
  "candidate_yoe": 5.0,
  "resume_score": 85.00,
  "parsed_resume": {
    "candidate_name": "John Doe",
    "email": "john.doe@example.com",
    "phone": "+1-555-0188",
    "summary": "5 years Java Backend Developer",
    "skills": ["Java", "Spring Boot", "PostgreSQL", "Docker"],
    "experience_years": 5.0,
    "education": ["B.Tech Computer Science"]
  },
  "matching_result": {
    "score_breakdown": {
      "skills_score": 40,
      "experience_score": 30,
      "education_score": 15,
      "overall_score": 85
    },
    "matched_skills": ["Java", "Spring Boot", "PostgreSQL"],
    "missing_skills": ["Kafka", "Redis"],
    "experience_match": true,
    "education_match": true,
    "reasoning": ["Candidate meets experience min (5 >= 3)", "Matched 3 core skills"]
  }
}
```

#### PATCH /api/v1/applications/{id}/status
**Purpose**: HR updates application status (`applied`, `interview_scheduled`, `interview_completed`, `shortlist_for_l1`, `rejected`).  
**Roles**: `hr`, `organization_admin`, `super_admin`  

---

### F. Interview Session & Analysis Endpoints

#### POST /api/v1/interview-sessions
**Purpose**: HR schedules an AI screening interview session (`interview_session`). Triggers internal call to `services/ai-screening` to generate static session questions (`generated_questions`).  
**Roles**: `hr`, `organization_admin`, `super_admin`  

```json
Request:
{
  "application_id": "555e4567-e89b-12d3-a456-426614174000",
  "interview_type": "screening_ai",
  "scheduled_at": "2026-08-05T10:00:00Z",
  "comment": "Initial AI screening call",
  "interview_metadata": {
    "gmeet_link": "https://meet.google.com/abc-defg-hij",
    "time_zone": "Asia/Kolkata"
  }
}

Response 201:
{
  "id": "666e4567-e89b-12d3-a456-426614174000",
  "application_id": "555e4567-e89b-12d3-a456-426614174000",
  "scheduled_by": "333e4567-e89b-12d3-a456-426614174000",
  "interview_type": "screening_ai",
  "status": "scheduled",
  "scheduled_at": "2026-08-05T10:00:00Z",
  "generated_questions": [
    {
      "id": 1,
      "question": "How have you handled container orchestration using Kubernetes in production?",
      "expected_keywords": ["Pods", "Deployments", "Services", "Autoscaling"],
      "example_depth": "Candidate should explain pod lifecycle and deployment manifests.",
      "follow_up": "Can you share a specific production issue you debugged?"
    }
  ]
}
```

#### GET /api/v1/interview-sessions/{id}
**Purpose**: Get details of interview session `{id}`.  
**Roles**: `hr`, `organization_admin`, `super_admin`  

#### PATCH /api/v1/interview-sessions/{id}/status
**Purpose**: Update session status (`scheduled`, `rescheduled`, `completed`, `no_show`, `cancelled`, `failed`).  
**Roles**: `hr`, `organization_admin`, `super_admin`  

#### GET /api/v1/interview-sessions/{id}/analysis
**Purpose**: Retrieve AI transcript screening report (`interview_analysis`) for a completed session.  
**Roles**: `hr`, `organization_admin`, `super_admin`  

```json
Response 200:
{
  "id": "888e4567-e89b-12d3-a456-426614174000",
  "interview_session_id": "666e4567-e89b-12d3-a456-426614174000",
  "application_id": "555e4567-e89b-12d3-a456-426614174000",
  "interview_type": "screening_ai",
  "recording_url": "https://media.attendee.dev/recordings/rec_99182.mp3",
  "analysis_result": {
    "overall_feedback": "Candidate demonstrated strong backend development skills.",
    "technical_summary": "Strong in Java and Spring Boot.",
    "communication_summary": "Clear communication with good confidence.",
    "skill_breakdown": {
      "Java": 9,
      "Spring Boot": 8,
      "PostgreSQL": 9,
      "Kafka": 5
    },
    "final_recommendation": "Shortlist for L1"
  },
  "question_answer": [
    {
      "question_id": 1,
      "question": "How have you handled container orchestration using Kubernetes in production?",
      "candidate_answer": "I deployed Pods, Services, and set up HPA scaling...",
      "score": 9
    }
  ],
  "created_at": "2026-08-05T10:35:00Z"
}
```

#### POST /api/v1/webhooks/attendee
**Purpose**: Webhook listener for Attendee meeting bot status, transcript, and audio recording. Ingests transcript Q&A and triggers `services/ai-screening` to populate `interview_analysis`.  
**Roles**: Public (Webhook Signature Validated)  

---

## 4. Internal Inter-Service Microservice APIs

These private internal endpoints are invoked exclusively over the internal cluster network between service modules (`apps/core-api` $\leftrightarrow$ `services/parsing-matching` & `services/ai-screening`).

---

### A. Parsing & Matching Microservice (`services/parsing-matching`)
* **Base URL**: `http://parsing-matching:8001/internal/v1`

#### POST /internal/v1/parse/jd
**Caller**: `apps/core-api`  
**Purpose**: Parses raw JD document/text into structured `parsed_jd` JSON.  

#### POST /internal/v1/parse/resume
**Caller**: `apps/core-api`  
**Purpose**: Parses uploaded candidate resume file into structured `parsed_resume` JSON.  

#### POST /internal/v1/match/resume-jd
**Caller**: `apps/core-api`  
**Purpose**: Evaluates `parsed_resume` against `parsed_jd` using Param.ai scoring algorithm. Returns overall `resume_score` and detailed `matching_result` JSON.  

---

### B. AI Screening Microservice (`services/ai-screening`)
* **Base URL**: `http://ai-screening:8002/internal/v1`

#### POST /internal/v1/screening/questions/generate
**Caller**: `apps/core-api`  
**Purpose**: Receives `parsed_jd` and `parsed_resume` for an application $\rightarrow$ Generates static session questions (`generated_questions`) tailored to candidate skill gaps.  

#### POST /internal/v1/screening/bot/dispatch
**Caller**: `apps/core-api` (5 mins before scheduled session time or HR manual trigger)  
**Purpose**: Dispatches Attendee.dev meeting bot to join the Google Meet URL. Returns `bot_id` and sets `interview_metadata`.  

```json
Request:
{
  "interview_session_id": "666e4567-e89b-12d3-a456-426614174000",
  "gmeet_link": "https://meet.google.com/abc-defg-hij",
  "bot_name": "EZScreen Screening Assistant"
}

Response 200:
{
  "bot_id": "bot_99182371a",
  "status": "dispatching",
  "dispatched_at": "2026-08-05T09:55:00Z"
}
```

#### POST /internal/v1/screening/audio/stt
**Caller**: `services/ai-screening` internal worker  
**Purpose**: Converts live audio stream into real-time text transcript tokens.  

```json
Request:
{
  "audio_chunk_base64": "<audio_stream>",
  "language": "en"
}

Response 200:
{
  "transcript_text": "I deployed Pods and configured Horizontal Pod Autoscaling...",
  "confidence": 0.96
}
```

#### POST /internal/v1/screening/audio/tts
**Caller**: `services/ai-screening` internal bot pipeline  
**Purpose**: Synthesizes AI question text or follow-up prompts into spoken audio stream for the Attendee meeting bot.  

```json
Request:
{
  "text": "How have you handled container orchestration using Kubernetes in production?",
  "voice_id": "en_us_professional_female"
}

Response 200:
{
  "audio_url": "https://media.ezscreen.io/tts/audio_9912.mp3",
  "duration_seconds": 5.2
}
```

#### POST /internal/v1/screening/analysis/evaluate
**Caller**: `apps/core-api` (upon receiving Attendee webhook transcript)  
**Purpose**: Runs `gemma4:31b` LLM evaluation on completed call transcript $\rightarrow$ Returns structured `analysis_result` and `question_answer` JSON payloads to populate `interview_analysis`.  

```json
Request:
{
  "transcript": [
    {"speaker": "Bot", "text": "How have you handled container orchestration using Kubernetes in production?"},
    {"speaker": "Candidate", "text": "I deployed Pods, Services, and configured HPA..."}
  ],
  "generated_questions": [ ... ]
}

Response 200:
{
  "analysis_result": {
    "overall_feedback": "Candidate demonstrated strong backend development skills.",
    "technical_summary": "Strong in Java and Spring Boot.",
    "communication_summary": "Clear communication with good confidence.",
    "skill_breakdown": {
      "Java": 9,
      "Spring Boot": 8,
      "PostgreSQL": 9,
      "Kafka": 5
    },
    "final_recommendation": "Shortlist for L1"
  },
  "question_answer": [
    {
      "question_id": 1,
      "question": "How have you handled container orchestration using Kubernetes in production?",
      "candidate_answer": "I deployed Pods, Services, and configured HPA...",
      "score": 9
    }
  ]
}
```
