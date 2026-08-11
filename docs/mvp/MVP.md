# MVP Technical Document - AI-Powered Recruitment Platform

> **Scope**: This document defines the MVP scope, technology decisions, implementation phases, and acceptance criteria for the AI-powered recruitment screening platform.
>
> **Source-of-Truth Hierarchy**: Requirements → System Design → MVP → Detailed Docs

---

## Table of Contents

1. [MVP Objective](#1-mvp-objective)
2. [Success Criteria](#2-success-criteria)
3. [Scope](#3-scope)
4. [Non-Goals](#4-non-goals)
5. [User Roles (MVP)](#5-user-roles-mvp)
6. [User Journeys](#6-user-journeys)
7. [Technology Decisions](#7-technology-decisions)
8. [Implementation Phases](#8-implementation-phases)
9. [API Reference](#9-api-reference)
10. [Data Model Reference](#10-data-model-reference)
11. [External Integrations](#11-external-integrations)
12. [AI Workflows](#12-ai-workflows)
13. [Error Handling](#13-error-handling)
14. [Testing Requirements](#14-testing-requirements)
15. [Acceptance Criteria](#15-acceptance-criteria)
16. [Deferred Capabilities](#16-deferred-capabilities)

---

## 1. MVP Objective

Deliver an AI-powered candidate screening and interview automation system (EZScreen) where HR can publish job descriptions, candidates apply with resumes, and the AI extracts, scores, and ranks candidates using a **Core Matching Engine**. The system provides a comprehensive **Visibility Layer** (Dashboards & per-skill match breakdown), automates **Interview Scheduling** via Google Calendar & gMeet APIs, auto-generates candidate-specific **Interview Questions** based on resume-JD gaps, and automates screening via an **Attendee Bot** on gMeet calls to capture transcripts and output screening analysis reports (`proceed` / `reject` / `next_round`).

**Core value**: Replace manual screening overhead with AI-driven candidate ranking, automated gMeet scheduling, and AI transcript screening.

---

## 2. Success Criteria

The MVP is complete when:

1. HR can create a JD (with document upload), review AI-extracted data, edit if needed, and publish
2. Candidates can browse published jobs and apply (guest, no account required) with a resume
3. AI extracts structured data from JDs and resumes, scores candidates 0-10, and generates explicit **Fit / No-Fit / Moderate Fit** recommendations with strengths & gaps
4. HR can view Visibility Dashboards (JD Management, Resume Management, Resume Scoring) with per-skill/criteria match breakdowns and sortable candidate lists
5. HR can shortlist candidates and schedule interviews via Google Calendar / gMeet API integration (generating meet links, sending invites, tracking candidate confirmation)
6. System auto-generates interview questions tailored to JD + resume gaps (technical, role & experience specific)
7. Attendee bot automatically joins the scheduled gMeet call, captures audio/transcript, and generates a screening report with competency signals, communication quality, technical depth, and a `proceed` / `reject` / `next_round` recommendation
8. All file downloads use signed URLs (no public file access)

---

## 3. Scope

### Included

| # | Capability | Category |
|---|-----------|----------|
| 1 | User registration & JWT login | Auth |
| 2 | Company & role seeding (initial setup) | Auth |
| 3 | JD creation with pre-signed upload URL | JD Pipeline |
| 4 | AI JD extraction (background) | JD Pipeline |
| 5 | HR review & edit of extracted data | JD Pipeline |
| 6 | JD publishing with validation gate (title + required_skills) | JD Pipeline |
| 7 | JD close & unpublish | JD Pipeline |
| 8 | JD creation - title only (manual mode) | JD Pipeline |
| 9 | Public job browsing (no auth) | Application |
| 10 | Guest application with pre-signed resume upload | Application |
| 11 | Unauthenticated application submission (no candidate account required) | Application |
| 12 | Candidate confirmation email | Application |
| 13 | AI resume extraction (background) | AI Scoring |
| 14 | AI matching & scoring benchmarked against logic (background) | Core Matching |
| 15 | Recommendation output (fit/no-fit/moderate, gaps, strengths) | Core Matching |
| 16 | Status update to screened | AI Scoring |
| 17 | Visibility Dashboards (JD Mgmt, Resume Mgmt, Resume Scoring, summary) | Visibility Layer |
| 18 | HR ranked applicant list (sort/filter/paginate by score) | Visibility Layer |
| 19 | HR applicant detail view with per-skill & per-criteria score breakdown | Visibility Layer |
| 20 | Status actions (shortlist, reject) | HR Review |
| 21 | Google Calendar & gMeet API integration (event creation, meet link gen, invites) | Scheduling |
| 22 | Scheduling logic (candidate availability, confirmation tracking via email link) | Scheduling |
| 23 | Gap-based question auto-generation (technical, role & experience specific) | Question Gen |
| 24 | Attendee bot gMeet integration (join call, capture transcript/audio) | Screening Auto |
| 25 | Screening transcript analysis (competency signals, communication, technical depth) | Screening Auto |
| 26 | Auto-generated screening report & recommendation (proceed/reject/next_round) | Screening Auto |
| 27 | File validation (MIME, magic bytes, size) | Security |
| 28 | Malware scanning | Security |
| 29 | Duplicate application prevention | Security |
| 30 | Idempotency-Key support | Reliability |
| 31 | RBAC (company-scoped data isolation) | Security |
| 32 | Frontend polling for processing status | UX |
| 33 | Token refresh | Auth |
| 34 | Password reset (forgot/reset) | Auth |
| 35 | Signed URLs for file downloads (15-min TTL) | Security |
| 36 | Minimal status change logging (audit) | Compliance |

---

## 4. Non-Goals & Excluded Features

The following are explicitly excluded from MVP / designated for **Next in Line**:

| Capability | Category | Reason / When |
|-----------|----------|---------------|
| Candidate account creation, registration, & login portal | Excluded | Candidates apply as guests via public links; all candidate communication happens via email |
| Candidate self-service application status tracking dashboard | Excluded | Out of scope - platform is designed for internal HR workflow |
| Param ATS Platform Integration (Push/Pull mechanism for JDs/Resumes) | Next in Line | Expansion scope after Core MVP validation |
| Multi-platform meeting bot support (MS Teams, Zoom) | Next in Line | Google Meet is the core target for MVP; Teams/Zoom deferred |
| Bulk status actions | Future Scope | Single actions suffice for MVP |
| URL-based JD import (`link` source_type) | Future Scope | Document upload sufficient |
| Email template customisation | Post-MVP | MVP uses hardcoded/seeded templates |
| User & company management UI | Post-MVP | Seed script for MVP setup |
| OAuth SSO | Future Scope | JWT auth sufficient for MVP |

---

## 5. User Roles (MVP)

| Role | How Created | Permissions |
|------|------------|------------|
| `super_admin` | Database seed | Full system access across all companies |
| `company_admin` | Database seed | Manage users within company, all company data |
| `hr_manager` | Registration + role assignment | Create/publish/close jobs, view all applicants, schedule interviews, view screening reports |
| `candidate` | N/A (Guest) | Applies to jobs via public link, receives gMeet invites & confirmation emails (no account required) |

**MVP Seeding**: The first company, admin user, and default roles are created via a seed script. Full user/company management UI is post-MVP.

---

## 6. User Journeys

### Journey 1: HR Creates and Publishes a JD

1. HR logs in → navigates to "Create Job"
2. Enters job title → requests upload URL → uploads PDF/DOCX document directly to S3
3. Submits form with `document_key` → System creates JD record (status: `draft`)
4. Background: AI worker extracts structured data from document
5. Frontend polls for completion → shows extracted data when ready
6. HR reviews extracted fields, edits if needed
7. HR clicks "Publish" → system validates title + required_skills exist
8. JD status changes to `published` → appears on public job list

### Journey 2: Candidate Applies (Guest Application)

1. Candidate views published job (no login required)
2. Enters name, email, phone → requests upload URL → uploads resume PDF directly to S3
3. Submits application form with `resume_key` → System creates application record (status: `applied`)
4. Application confirmation email sent to candidate
5. Background: AI worker parses resume data → matches against JD using benchmarked rules → scores candidate
6. Application status updated to `screened` (visible on HR Visibility Dashboard)

### Journey 3: HR Reviews Candidates & Schedules Interview

1. HR opens Resume Scoring Dashboard for a JD
2. Sees ranked list sorted by AI matching score with per-skill breakdown & recommendation summary
3. HR shortlists a candidate → clicks "Schedule Interview"
4. System calls Google Calendar API → creates event, generates gMeet link, and sends email invite to candidate
5. System auto-generates interview questions based on candidate-JD gaps

### Journey 4: Attendee Bot Screening Automation

1. Scheduled interview time arrives → System dispatches Attendee bot to gMeet call
2. Bot joins call, records audio, and streams dual-channel transcript
3. Post-call: AI evaluates transcript (competency signals, communication, technical depth)
4. System outputs Screening Analysis Report with `proceed` / `reject` / `next_round` recommendation for HR review
4. Can filter by status, score range, experience range
5. Clicks a candidate → sees full detail with score breakdown
6. Reviews matched skills (green), missing skills (red), experience timeline
7. Shortlists or rejects the candidate

### Journey 5: HR Schedules Interview (Direct Invite)

1. HR selects a shortlisted candidate
2. Enters meeting link, date/time
3. System creates interview record (status: `scheduled`)
4. A new session with meeting link created for the candidate
5. Email sent to candidate with meeting link and time
6. Candidate's resume and the JD parsed data fetched by interview screening
7. Questions generated from this parsed data and stored in DB for the session

### Journey 6: Candidate Joins Interview

1. Candidate joins the interview on scheduled time
2. A human (HR) also joins the same interview on scheduled time
3. Interview session created and started
4. AI interviewer starts with Interview questions of that session
5. Candidate and AI interviewer speak in turn
6. Session ends upon time completion
7. Transcription and Audio of the meeting stored
8. Output of interview screening generated based on the performance metrics
9. Candidate's evaluation report sent to dahsboard

### Journey 7: HR reviews candidate

1. HR reviews candidate's evaluation report on dashboard
2. HR allows candidate for L1 or rejects candidate
3. Candidate's data deleted according to rentention policy

---

## 7. Technology Decisions

| Component | Decision | Rationale |
|-----------|----------|-----------|
| **Backend framework** | FastAPI (Python) | Async-native, auto-generated OpenAPI, Pydantic aligns with JSONB schemas, strong LLM SDK support |
| **Frontend framework** | React (JavaScript) | Team familiarity, rich ecosystem, SPA model fits this product |
| **Database** | PostgreSQL | JSONB support required for AI-extracted data, proven reliability |
| **Message broker** | Redis | Serves as both broker and result backend, simple setup |
| **Task queue** | To be evaluated: Celery, Dramatiq, ARQ | Redis-backed. Final choice during implementation setup |
| **LLM provider** | OpenAI (GPT-4o) primary, explore alternatives | Strongest structured JSON output. Ollama option for local dev to avoid API costs |
| **Email service** | SendGrid or Resend | Simple API, free tier for MVP volumes |
| **Object storage** | S3-compatible (MinIO for local dev) | S3 API is the standard. MinIO for Docker-based local dev |
| **Repository structure** | Monorepo | Simplifies coordination during early development |
| **Containerisation** | Docker | Mandatory per architecture - same images across all environments |
| **Audit logging (MVP)** | Minimal status change logging | Records who changed what status and when. Full audit_logs schema deferred |

---

## 8. Implementation Phases

### Phase 1: Foundation

**Goal**: Scaffolding, auth, database, Docker setup

- Project scaffolding (FastAPI + React)
- Docker Compose setup (backend, worker, PostgreSQL, Redis, MinIO)
- Database migrations (companies, roles, users, user_roles)
- Seed script (first company, admin user, default roles)
- JWT auth (register, login, refresh, logout, forgot/reset password, me)
- RBAC middleware
- Basic health check endpoint

**Testable outcome**: User can register, login, get token, access protected endpoint.

### Phase 2: JD Pipeline

**Goal**: JD creation → AI extraction → HR review → publish

- JD CRUD endpoints
- Pre-signed S3 URL generation for document upload
- Background worker: `parse-jd` task (document parsing + LLM extraction)
- JD status machine (draft → processing → draft_parsed → published → closed)
- Publishing gate validation (title + required_skills)
- Polling endpoint for frontend status checking
- Frontend: JD creation form, extraction review page, publish flow

**Testable outcome**: HR uploads a JD document → AI extracts data → HR reviews and publishes → JD appears on public job list.

### Phase 3: Application Pipeline

**Goal**: Candidate applies → AI scores → application ranked

- Public job browsing endpoints
- Guest application endpoint (no auth)
- Ghost user creation
- Pre-signed S3 URL generation for resume upload
- Background worker: `parse-resume` task → chained `match-candidate` task
- Matching score calculation and denormalisation
- Application status machine
- Duplicate application prevention (composite unique constraint)
- Signed URL generation for file downloads
- Frontend: public job list, job detail, application form, polling for processing

**Testable outcome**: Candidate applies → AI scores resume → application appears in HR's ranked list.

### Phase 4: HR Review & Scheduling

**Goal**: HR reviews candidates → shortlists/rejects → schedules interviews

- Applicant list endpoint with sort/filter/pagination
- Application detail endpoint with score breakdown + signed resume URL
- Status actions (shortlist, reject) with minimal audit logging
- Interview scheduling - Option A (direct invite)
- Candidate account creation (register + ghost user upgrade)
- Candidate application status view
- Frontend: ranked applicant list, detail page, status actions, interview scheduling form, candidate dashboard

**Testable outcome**: HR views ranked list → opens detail → shortlists → sends interview invite → candidate receives email.

### Phase 5: Polish & Deploy

**Goal**: Edge cases, emails, error handling, deployment

- Application confirmation email (send-email task)
- Error handling for all failure scenarios
- Rate limiting on public endpoints
- CORS configuration
- Input validation refinement
- End-to-end testing
- Deployment configuration

**Testable outcome**: Full user journey works end-to-end in a staging environment.

---

## 9. API Reference

> Full endpoint contracts are documented in [API_SPEC.md](../architecture/API_SPEC.md).

**MVP Endpoints**:

| Group | Endpoints |
|-------|----------|
| Auth | register, login, refresh, logout, forgot-password, reset-password, me, update-me |
| Jobs | list, create, get, update, delete, status-change, applicants |
| Public | browse-jobs, view-job, apply |
| Applications | list, get-detail, status-change |
| Interviews | create, get, update, cancel |
| Interview (public) | view-slots, select-slot |
| System | health |

---

## 10. Data Model Reference

> Full entity definitions, ER diagram, and JSONB schemas are documented in [DB_DESIGN.md](../architecture/DB_DESIGN.md).

**MVP Entities**: companies, roles, users, user_roles, job_descriptions, applications, interview_schedules, email_templates (seeded)

---

## 11. External Integrations

| Service | Purpose | MVP Config | Local Dev Alternative |
|---------|---------|-----------|----------------------|
| **LLM (OpenAI)** | JD extraction, resume parsing, matching | `OPENAI_API_KEY` env var | Ollama (optional, to reduce API costs) |
| **Object Storage (S3)** | JD documents, resumes | `S3_BUCKET`, `S3_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | MinIO container in Docker Compose |
| **Email (SendGrid/Resend)** | Confirmation, interview invites | `EMAIL_API_KEY`, `EMAIL_FROM` | Console logging or Mailhog container |
| **Message Broker (Redis)** | Task queue for async processing | `REDIS_URL` | Redis container in Docker Compose |

---

## 12. AI Workflows

> Full pipeline details, prompt engineering tables, and scoring formula are documented in [AI_PROCESSING.md](../architecture/AI_PROCESSING.md).

**MVP Constraints**:
- LLM provider: OpenAI GPT-4o (configurable via env var)
- All prompts return structured JSON matching the JSONB schema
- Prompt versioning: store prompt template version in task metadata for traceability
- Matching score formula: `(skills × 0.40 + experience × 0.35 + education × 0.25) × 10`
- `parse-resume` auto-chains to `match-candidate` - no manual trigger needed

---

## 13. Error Handling

| Scenario | Expected Behaviour |
|----------|-------------------|
| AI extraction fails (LLM timeout/error) | Retry 3× with exponential backoff. On final failure: status → `extraction_failed`, HR notified in-app, retry button shown |
| File too large (>10MB) | Rejected directly by S3 via pre-signed URL constraints |
| Invalid file type | Handled by worker: fails task, status → `extraction_failed` |
| Duplicate application (same email + same JD) | Reject with 409, clear error message |
| Network retry (duplicate submission) | `Idempotency-Key` header returns original response |
| LLM returns invalid JSON | Retry (treated as task failure). After max retries, DLQ + status = failed |
| Publishing without required_skills | Reject with 422, explain what is missing |
| Unauthorized access to another company's data | 403 (RBAC enforces company-scoped queries) |

---

## 14. Testing Requirements

### Unit Tests (Required for MVP)

- Matching score formula (all weight combinations, edge cases with 0 scores)
- JD status machine (all valid transitions, reject invalid)
- Application status machine (all valid transitions, reject invalid)
- RBAC permission checks (each role, company isolation)
- File validation (MIME type, magic bytes, size)
- Ghost user creation and linking logic

### Integration Tests (Required for MVP)

- JD creation → AI extraction → status update (mocked LLM)
- Application submission → resume parsing → matching → scoring (mocked LLM)
- Full JWT lifecycle (register → login → refresh → logout)
- Duplicate application rejection
- Company-scoped data isolation (cross-company access denied)

### AI Quality Tests

- AI regression fixtures: fixed JD + resume pairs with expected score ranges
- Verify extracted fields match expected structure
- Verify matching scores are within acceptable ranges for known inputs

> Full testing strategy is documented in [SYSTEM_DESIGN.md](../architecture/SYSTEM_DESIGN.md) §13.

---

## 15. Acceptance Criteria

These are the MVP-relevant acceptance criteria from the Requirements Document:

| ID | Criteria | Implementation Phase |
|----|---------|---------------------|
| AC-001 | JD creation with document → 201 in <500ms → extracted_data populated within 2 min | Phase 2 |
| AC-002 | JD creation title-only → record created immediately → extracted_data empty | Phase 2 |
| AC-003 | Publishing gate: required_skills required, else 422 | Phase 2 |
| AC-004 | Guest application → 201 in <500ms → confirmation email sent | Phase 3 |
| AC-005 | Duplicate application → 422 with clear error | Phase 3 |
| AC-006 | Resume scoring → status = screened, score 0-10, job_fit_analysis populated | Phase 3 |
| AC-007 | Ranked list: 10+ applicants sorted by score, shows name, score, skills bar, experience, status | Phase 4 |
| AC-008 | Direct interview invite → email within 2 min with meeting link and time | Phase 4 |

---

## 16. Deferred Capabilities

| Capability | Target | Reason for Deferral |
|-----------|--------|-------------------|
| Interview self-scheduling (Option B) | Post-MVP | Adds token-based public pages, deadline handling |
| Bulk status actions | Future Scope | Single actions suffice for MVP |
| URL-based JD import | Future Scope | Document upload sufficient |
| Email template customisation | Post-MVP | Seeded templates sufficient |
| JD/application reprocessing | Post-MVP | HR can edit fields manually |
| User & company management UI | Post-MVP | Seed script for MVP setup |
| Job analytics | Future Scope | No requirement |
| Comprehensive audit logging | Future Scope | Minimal status logging in MVP |
| Reminder & deadline notifications | Future Scope | Only immediate notifications in MVP |
| Calendar .ics attachments | Future Scope | Not specified in design |
| Advanced notifications | Future Scope | Not in MVP scope |
| OAuth SSO | Future Scope | Not in requirements |
| WebSocket updates | Future Scope | Polling sufficient |

