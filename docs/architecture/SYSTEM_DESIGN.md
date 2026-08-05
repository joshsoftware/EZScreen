# AI-Powered Recruitment Platform - EZScreen System Design

## 1. Overview

### Purpose
An AI-powered recruitment platform that automates the candidate screening process by:
- Parsing job descriptions and extracting key requirements
- Processing candidate resumes and extracting qualifications
- Automatically filtering candidates based on JD-resume matching
- Facilitating interview scheduling for shortlisted candidates

### Key Stakeholders
- **HR/Recruiters**: Publish jobs, review candidates, schedule interviews
- **Admins**: System-wide access and management
- **Candidates**: Browse jobs, apply, schedule interviews (optional account)

### Core Value Proposition
Eliminate manual screening overhead with AI-driven candidate resume matching and screening.

---

## 2. System Architecture

### High-Level Architecture

```mermaid
flowchart TB
    subgraph FE["Frontend Presentation Layer"]
        UI["React Single Page Application (SPA)<br>Super Admin, Org Admin, Org HR & Candidate Portals"]
    end

    subgraph GW["API Gateway"]
        Gateway["Nginx API Gateway<br>Subdomain Resolution (org.ezscreen.io) & JWT Auth"]
    end

    subgraph BACKEND["Core Backend Application"]
        FastAPI["FastAPI Core Backend<br>User Management, Orgs, JDs & Interview Sessions"]
    end

    subgraph AI["Modular AI Screening Service"]
        AIService["AI Screening Microservice<br>STT - LLM (gemma4:31b) - TTS Pipeline"]
    end

    subgraph DATA["Shared Data & Storage (MVP)"]
        DB[("PostgreSQL Database")]
        S3[("S3 Object Storage")]
    end

    subgraph EXT["External Integrations"]
        GCal["Google Calendar API (gMeet)"]
        Attendee["Attendee.dev API (gMeet Bot)"]
    end

    UI --> Gateway
    Gateway --> FastAPI
    FastAPI <--> AIService

    FastAPI <--> DB
    FastAPI <--> S3

    AIService <--> DB
    AIService <--> S3

    FastAPI --> GCal
    AIService <--> Attendee

    classDef fe fill:#e3f2fd,stroke:#1565c0,stroke-width:2px,color:#000
    classDef gw fill:#fff3e0,stroke:#e65100,stroke-width:2px,color:#000
    classDef backend fill:#f3e5f5,stroke:#4a148c,stroke-width:2px,color:#000
    classDef ai fill:#ede7f6,stroke:#311b92,stroke-width:2px,color:#000
    classDef data fill:#e8f5e9,stroke:#1b5e20,stroke-width:2px,color:#000
    classDef ext fill:#fffde7,stroke:#f57f17,stroke-width:2px,color:#000

    class UI fe
    class Gateway gw
    class FastAPI backend
    class AIService ai
    class DB,S3 data
    class GCal,Attendee ext
```

### Architecture Patterns

| Pattern | Applied to | Rationale |
| :--- | :--- | :--- |
| **Modular Monolith** | Whole System | Code is structured into decoupled modules inside a Monorepo. Enables fast MVP deployment with a shared database while preserving clear boundaries for independent microservice extraction. |
| **Domain Isolation** | Core API, Parsing, Screening | `core-api`, `parsing-matching`, and `ai-screening` operate as isolated domain packages with strict contract boundaries. |
| **Shared Storage MVP** | PostgreSQL & S3 | Shared database across modules for single-transaction ACID consistency and high-speed relational JOINs. |

---

### Modular Monolith & Monorepo Structure

The platform is designed as a **Modular Monolith inside a Monorepo**. This guarantees clean separation of concerns without the operational complexity of distributed microservices for MVP.

#### Service Module Responsibilities

1. **Core Backend Application (`apps/core-api`)**:
   * System gatekeeper handling Authentication, Multi-tenant Organization Scoping (`organization_id`), User Provisioning, Public Job Board API, Interview Scheduling, and Webhook routing.

2. **Parsing & Matching Engine (`services/parsing-matching`)**:
   * Pure document parsing and matching engine. Extracts structured `parsed_jd` requirements, parses candidate resumes (`parsed_resume`), and computes Param.ai candidate-JD matching scores (`matching_result`).
   * *Standalone Capability*: Can be packaged and deployed independently as a "Resume & JD Parsing API".

3. **AI Screening Microservice (`services/ai-screening`)**:
   * Handles static interview question generation (`generated_questions`), STT-LLM (`gemma4:31b`)-TTS conversation pipeline, Attendee bot coordination, and transcript Q&A evaluation (`interview_analysis`).
   * *Standalone Capability*: Can be deployed independently on GPU infrastructure for AI video/voice interview execution.
---

## 3. Technology Stack

The following technologies have been selected for the platform to balance rapid MVP development with long-term scalability.

---

### Frontend

| Component | Selection | Rationale |
| :--- | :--- | :--- |
| Framework | React (JavaScript) | Team familiarity, rich ecosystem, SPA model fits this product |
| UI Library | Modern React Library + TailwindCSS | Rapid styling and responsive design |
| File Upload | Pre-signed S3 URLs via frontend | Bypasses backend server to save bandwidth |
| Other Tooling | Vite, Axios, React Router, Vitest | Standard React ecosystem defaults |

---

### Backend

The backend handles REST APIs, authentication, job orchestration, async task dispatch, and AI processing logic. Python is chosen because the AI/ML ecosystem is strongest in Python.

| Component | Selection | Rationale |
| :--- | :--- | :--- |
| Framework | FastAPI (Python) | Async-native, auto-generated OpenAPI, strong LLM SDK support |
| Schema Validation | Pydantic | Aligns perfectly with FastAPI and JSONB schemas |
| API Documentation | Auto-generated via FastAPI | Zero-maintenance Swagger UI |
| Email Service | SendGrid or Resend | Simple API, generous free tier for MVP volumes |
| Data Access | SQLAlchemy | Standard for FastAPI |
| Auth & Crypto | python-jose, passlib (bcrypt) | Proven security |

---

### AI Processing

AI processing runs as a module within the backend codebase. All AI tasks are executed by background workers to ensure long-running LLM calls never block API responses.

| Component | Selection | Rationale |
| :--- | :--- | :--- |
| LLM Provider / Model | **`gemma4:31b`** (via Ollama / Hosted API) | Selected open-weight 31B parameter model providing high-quality structured JSON output |
| Local LLM Runner | Ollama (with `gemma4:31b`) | Local runner option for development & self-hosted deployments |
| Document Parsing | docling | Python-native text extraction |
| Orchestration | Custom prompt pipeline / Piepcat | Simple is better for MVP |
| Meeting Bot | Attendee.dev API | Headless gMeet meeting bot for recording dual-channel audio & transcript |

---

### Data Layer

| Component | Selection | Rationale |
| :--- | :--- | :--- |
| Primary Database | PostgreSQL | JSONB support required for AI-extracted data, proven reliability |
| Object Storage | S3-compatible | S3 API is the standard. MinIO simplifies Docker-based local dev |
| Key-Value Data Store | - (To Be Decided) | To be evaluated based on lightweight storing requirements |

> **Storage note**: Object storage is the single source of truth for all uploaded files (JDs and resumes). A local MinIO container is used during development. In production, a managed S3-compatible service is used directly.

---

### Key Constraints That Drive Choices

The following requirements constrain the option space regardless of preference:

1. **JSONB support** - the database must support a flexible JSON column type. This rules out MySQL before version 5.7 and most NoSQL databases as a primary store.
2. **S3-compatible object storage in production** - all environments above local dev must use a cloud-managed object storage service. Local emulators are not permitted in staging or production.
3. **AI processing isolation via task queue** - all LLM-calling code runs in background worker processes, not in the API request/response cycle. Workers are separate OS processes running the same codebase with a different entrypoint. This prevents LLM latency from degrading API response times and allows workers to be scaled independently based on queue depth.
4. **Containerisation is mandatory** - every component ships as a Docker image. This applies to all environments including development, so environment parity is maintained from day one.

---

## 4. Database Design

> **Full Reference**: Entity definitions, column details, ER diagram, JSONB schemas, indexing strategy, and data lifecycle are documented in [DB_DESIGN.md](DB_DESIGN.md).

### Entity Summary

| Entity | Purpose | Phase |
| --- | --- | --- |
| `organizations` | Multi-tenant organization records (`name`, `domain`, `logo_url`) | MVP |
| `users` | All user accounts (`super_admin`, `organization_admin`, `hr`, `candidate`) | MVP |
| `job_descriptions` | JD records with `parsed_jd` JSONB for AI-extracted requirements | MVP |
| `applications` | Candidate applications with `parsed_resume` & `matching_result` JSONB | MVP |
| `interview_session` | Session-based AI interview scheduling & static question sets (`generated_questions`) | MVP |
| `interview_analysis` | AI screening report, Q&A transcript analysis (`question_answer`), and call recording URL | MVP |

### Key Design Decisions

1. **JSONB for Flexible AI Data**: `parsed_jd`, `parsed_resume`, `matching_result`, `generated_questions`, `analysis_result`, and `question_answer` use PostgreSQL's JSONB type
   - Allows AI extraction schema evolution without complex SQL migrations
   - Enables efficient querying with GIN indexes
   - Perfect for storing rich AI feedback, score breakdowns, and dual-channel transcripts

2. **Status-Driven Workflows**: Enforces state machines via PostgreSQL ENUM types:
   - `user_status`: `active`, `inactive`, `suspended`
   - `user_role`: `super_admin`, `organization_admin`, `hr`, `candidate`
   - `job_status`: `draft`, `published`, `closed`
   - `application_status`: `applied`, `interview_scheduled`, `interview_completed`, `shortlist_for_l1`, `rejected`
   - `interview_status`: `scheduled`, `rescheduled`, `completed`, `no_show`, `cancelled`, `failed`

3. **Multi-Tenancy & Role Isolation**:
   - `organization_admin` and `hr` are bound strictly to one organization (`organization_id NOT NULL`).
   - `super_admin` (global owner) and `candidate` operate across system scopes (`organization_id NULL`).

4. **Session-Based Interviewing & Analysis Separation**:
   - `interview_session` handles meeting metadata (gMeet URL, bot dispatch state, scheduled times, static questions).
   - `interview_analysis` handles post-interview screening output (Q&A transcripts, skill scores, overall recommendation, audio/video recording URLs).

---

## 5. API Design

> **Full Reference**: Endpoint contracts, request/response schemas, role access per endpoint, query parameters, error format, and phase classification are documented in [API_SPEC.md](API_SPEC.md).

### API Design Principles

- **RESTful**: All endpoints follow REST conventions with resource-based URLs
- **Versioned**: All routes prefixed with `/api/v1/`
- **RBAC-Protected**: Role-based access control on all authenticated endpoints
- **Idempotent**: Resource creation endpoints support `Idempotency-Key` header
- **No `/admin/` namespace**: Administrative operations use standard resource URLs (`/users`, `/companies`, `/roles`) with RBAC determining scope

### API Groups

| Group | Base Path | Auth | Key Endpoints | Phase |
|-------|-----------|------|---------------|-------|
| Authentication | `/api/v1/auth/` | Public | register, login, refresh, logout, forgot-password, reset-password, me | MVP |
| Job Descriptions | `/api/v1/jobs/` | JWT | CRUD, status change, applicant list | MVP |
| Public Browsing | `/api/v1/public/jobs/` | None | Browse jobs, view job, apply | MVP |
| Applications | `/api/v1/applications/` | JWT | List, detail (with signed resume URL), status change | MVP |
| Interview Scheduling | `/api/v1/interviews/` | JWT / Token | Create invite, self-scheduling via token | MVP |
| User & Company Mgmt | `/api/v1/users/`, `/companies/`, `/roles/` | JWT (RBAC) | CRUD for users, companies, roles | Post-MVP |
| System | `/api/v1/system/` | JWT (super_admin) | Health check | MVP |

### Key Query Capabilities (Applicant List)

The applicant list endpoint (`GET /jobs/{id}/applicants`) supports:
- **Sort**: by score (default), date, name, experience
- **Filter**: by status, score range, experience range
- **Pagination**: max 50 per page

---

## 6. Authentication & Authorization

### Authentication Strategy

**Two-tier Authentication**:
1. **Guest Access**: Candidates can browse and apply without accounts
2. **JWT Authentication**: For registered users (HR, Admin)

### JWT Implementation

Tokens are stateless JWTs signed with a secret key. Two token types are used:

| Token | Stored in | TTL | Purpose |
|-------|----------|-----|---------|
| Access token | Memory (not localStorage) | 15-30 minutes | Authenticates API requests |
| Refresh token | httpOnly cookie | 7 days | Issues new access tokens silently |

**Access token payload**:

| Claim | Description |
|-------|-------------|
| `sub` | User UUID |
| `email` | User email address |
| `roles` | Array of role names for this user |
| `company_id` | Company UUID - enforces tenant isolation |
| `iat` | Issued at timestamp |
| `exp` | Expiry timestamp |

**Token refresh flow**: When an API call returns 401, the client silently sends the refresh token to `POST /auth/refresh`. If valid, a new access token is returned and the original request is retried. If invalid or expired, the session is cleared and the user is sent to login.

**Token invalidation**: On logout, the refresh token is revoked server-side. The revoked token's JTI is stored in a revocation table in the database with an expiry timestamp matching the token's remaining lifetime. A background task periodically cleans up expired entries.

### Authorization - Role-Based Access Control (RBAC)

#### Roles & Permissions

| Role | Scope | Key permissions |
|------|-------|----------------|
| `super_admin` | All companies | Full system access - manage companies, users, roles, system config |
| `admin` | Own company | Manage users within company, view all company data |
| `hr_manager` | Own company | Create/publish/close jobs, view all applicants, schedule interviews |
| `candidate` | Own data | Browse published jobs, submit applications, view own application status |

Guest (unauthenticated) access is permitted only on:
- `GET /api/v1/public/jobs` - browse published jobs
- `GET /api/v1/public/jobs/:id` - view job detail
- `POST /api/v1/public/jobs/:id/apply` - submit application

All other endpoints require a valid access token.

#### Permission Enforcement

Permissions are checked at two layers:

1. **Route layer** - middleware validates the token and extracts roles before the request reaches any handler. Requests with missing or invalid tokens are rejected with 401 before any business logic runs.

2. **Resource layer** - handlers verify the authenticated user's company matches the resource's company. An HR user from Company A cannot access jobs or applicants from Company B even with a valid token. This is enforced by automatically scoping all database queries to the authenticated user's `company_id`.

For user and company management endpoints, the same RBAC middleware determines scope: `super_admin` sees all companies and users; `admin` sees only users within their own company. The URL structure reflects the resources (`/users`, `/companies`), and the authorization layer determines what the caller can see and do.

---

## 7. Core Features & Workflows

---

### Workflow 1: Job Description Parsing & Publishing

```mermaid
sequenceDiagram
    actor HR as HR User
    participant F as Frontend (SPA)
    participant B as Backend API (FastAPI)
    participant AI as AI Parsing Engine (gemma4:31b)

    HR->>F: Upload raw JD file (PDF/DOCX) or paste text
    F->>B: POST /api/v1/jobs/parse
    Note over B,AI: Direct text/document parsing & AI extraction
    B->>AI: Extract title, skills, experience_min/max, parsed_jd JSON
    AI-->>B: Extracted JSON payload
    B-->>F: 200 OK (returns parsed fields directly to UI form)
    
    Note over HR,F: HR inspects & updates parsed fields directly in UI
    HR->>F: Click "Save & Publish Job"
    F->>B: POST /api/v1/jobs (with edited fields & status = published)
    Note over B: Save Job Description record in DB
    B-->>F: 201 Created
    F-->>HR: Confirmed (Job now live on public subdomain portal)
```

**JD status flow**:
```mermaid
stateDiagram
  direction TB
  classDef Aqua stroke-width:1px,stroke-dasharray:none,stroke:#46EDC8,fill:#DEFFF8,color:#378E7A;
  classDef Peach stroke-width:1px,stroke-dasharray:none,stroke:#FBB35A,fill:#FFEFDB,color:#8F632D;
  classDef Pine stroke-width:1px,stroke-dasharray:none,stroke:#254336,fill:#27654A,color:#FFFFFF;
  classDef Ash stroke-width:1px,stroke-dasharray:none,stroke:#999999,fill:#EEEEEE,color:#000000;
  draft --> published
  published --> closed
  published --> draft:(unpublish)
  class draft Peach
  class published Pine
  class closed Ash
```

> **Direct Parsing Workflow**: When HR uploads a JD file or pastes text, the backend parses the requirements immediately and returns the extracted fields directly to the frontend. HR can adjust any requirements directly in the UI before saving and publishing. No S3 storage is required for job descriptions.

### Workflow 2: Candidate Application & AI Resume Scoring

```mermaid
---
config:
  theme: redux-color
---
sequenceDiagram
    actor C as Candidate (Guest)
    participant F as Frontend (SPA)
    participant B as Backend API
    participant Q as Job Queue
    participant W as Worker
    actor HR as HR User

    C->>F: Browse org jobs ({org}.ezscreen.io)
    F->>B: GET /api/v1/public/jobs (Host: acme.ezscreen.io)
    B-->>F: Subdomain-scoped job list
    F-->>C: Display published jobs
    
    C->>F: Request resume upload URL
    F->>B: POST /api/v1/public/jobs/:id/upload-url
    B-->>F: Pre-signed S3 URL
    F->>S3: Upload resume directly to S3
    
    C->>F: Apply (name, email, phone, resume_key)
    F->>B: POST /api/v1/public/jobs/:id/apply
    Note over B: Save application record<br>status = applied
    B-->>F: Response (201 Created)
    F-->>C: Application confirmation
    
    B->>Q: Enqueue parse-resume job
    Q->>W: Dispatch
    Note over W: Download resume from S3<br>Extract qualifications & skills<br>Match against JD requirements<br>Calculate Param.ai score (0-10)<br>Generate fit recommendation & gaps<br><br>Update DB record<br>status = resume_screened
    
    HR->>F: Open job candidate dashboard
    F->>B: GET /api/v1/jobs/:id/applicants
    B-->>F: Ranked candidate list with resume matching scores
    F-->>HR: Displays ranked list with fit recommendations
```

**Application status flow**:
```mermaid
stateDiagram-v2
    applied --> processing
    processing --> resume_screened
    resume_screened --> shortlist_for_l1 : (HR shortlists)
    resume_screened --> rejected : (HR rejects)
    resume_screened --> interview_scheduled : (HR schedules interview)
    shortlist_for_l1 --> interview_scheduled : (HR schedules interview)
    interview_scheduled --> interview_completed : (Attendee bot captures transcript)
    interview_completed --> shortlisted : (Post-screening recommendation)
    interview_completed --> rejected : (Outcome)

    %% --- Class Definitions ---
    classDef frontend fill:#bbdefb,stroke:#1976d2,stroke-width:2px,color:#000
    classDef async fill:#b2dfdb,stroke:#00796b,stroke-width:2px,color:#000
    classDef apiNode fill:#ffe0b2,stroke:#f57c00,stroke-width:2px,color:#000
    classDef success fill:#c8e6c9,stroke:#388e3c,stroke-width:2px,color:#000
    classDef action fill:#fff9c4,stroke:#fbc02d,stroke-width:2px,color:#000
    classDef rejected fill:#fce4ec,stroke:#f48fb1,stroke-width:2px,color:#000

    %% --- Applying Classes to States ---
    class applied frontend
    class processing async
    class resume_screened apiNode
    class shortlist_for_l1 success
    class interview_scheduled action
    class interview_completed action
    class shortlisted success
    class rejected rejected
```

### Workflow 3: Session-Based Interview Scheduling, Auto Question Generation & Bot Screening

```mermaid
---
config:
  theme: redux-color
---
sequenceDiagram
    actor HR as HR User
    participant F as Frontend (SPA)
    participant B as Backend API
    participant GCal as Google Calendar API
    actor C as Candidate
    participant Q as Task Queue
    participant W as Worker
    participant Bot as Attendee.dev Bot

    HR->>F: Select candidate -> Schedule Interview Session
    F->>B: POST /api/v1/interview-sessions
    Note over B: 1. Create interview_session record<br>2. Call GCal API -> Create event & gMeet link<br>3. Send email invite to candidate<br>4. Auto-enqueue generate-questions task<br>status = interview_scheduled
    B-->>F: Response (Session created + gMeet link)
    F-->>HR: Interview Scheduled Confirmed
    B-->>C: Email Invite with gMeet link

    B->>Q: Enqueue generate-session-questions task (Auto)
    Q->>W: Dispatch
    Note over W: Analyze candidate resume vs JD gaps & match score<br>Auto-generate technical & role-specific questions for session<br>Store questions linked to interview_session_id

    Note over Bot,C: Scheduled Interview Time Arrival
    B->>Bot: POST /api/v1/interview-sessions/:id/bot/dispatch
    Bot->>gMeet: Join gMeet video call
    Note over Bot: Record dual-channel audio & transcript

    Bot->>B: POST /api/v1/webhooks/attendee (transcript complete)
    Note over B: Update session status = interview_completed<br>Enqueue transcript analysis worker
    B->>Q: Enqueue transcript-analysis task
    Q->>W: Dispatch
    Note over W: Evaluate competency signals,<br>communication score & technical depth<br>Generate screening report & recommendation
    
    HR->>F: View Session Screening Report & Questions
    F->>B: GET /api/v1/interview-sessions/:id/screening-report
    B-->>F: Full AI Screening Report, Generated Questions & Recommendation
    HR->>F: Update status (PATCH /api/v1/applications/:id/status -> shortlist_for_l1 or rejected)
```

---
