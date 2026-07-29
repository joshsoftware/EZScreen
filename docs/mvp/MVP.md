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

Deliver an AI-powered candidate screening system where HR can publish job descriptions, candidates can apply with resumes, and the AI automatically extracts, scores, and ranks candidates - enabling HR to review a ranked list and schedule interviews for top candidates.

**Core value**: Replace manual resume screening with AI-driven candidate ranking.

---

## 2. Success Criteria

The MVP is complete when:

1. HR can create a JD (with document upload), review AI-extracted data, edit if needed, and publish
2. Candidates can browse published jobs and apply (guest, no account required) with a resume
3. AI extracts structured data from JDs and resumes, scores candidates 0-10, and ranks them
4. HR can view ranked applicants sorted by AI matching score with score breakdown
5. HR can shortlist or reject candidates and schedule interviews (direct invite)
6. Candidates can create an account to track application status
7. Confirmation email is sent on application submission
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
| 11 | Ghost user creation | Application |
| 12 | Candidate account creation & status tracking | Application |
| 13 | Application confirmation email | Application |
| 14 | AI resume extraction (background) | AI Scoring |
| 15 | AI matching & scoring (background) | AI Scoring |
| 16 | Status update to screened | AI Scoring |
| 17 | HR ranked applicant list (sort/filter/paginate) | HR Review |
| 18 | HR applicant detail view with score breakdown | HR Review |
| 19 | Status actions (shortlist, reject) | HR Review |
| 20 | Interview scheduling - direct invite (Option A) | Scheduling |
| 21 | File validation (MIME, magic bytes, size) | Security |
| 22 | Malware scanning | Security |
| 23 | Duplicate application prevention | Security |
| 24 | Idempotency-Key support | Reliability |
| 25 | RBAC (company-scoped data isolation) | Security |
| 26 | Frontend polling for processing status | UX |
| 27 | Token refresh | Auth |
| 28 | Password reset (forgot/reset) | Auth |
| 29 | Signed URLs for file downloads (15-min TTL) | Security |
| 30 | Minimal status change logging (audit) | Compliance |

---

## 4. Non-Goals

The following are explicitly excluded from MVP:

| Capability | Reason | When |
|-----------|--------|------|
| Interview self-scheduling (Option B) | Adds complexity (token pages, deadlines) | Post-MVP |
| Bulk status actions | Convenience feature - single actions suffice | Future Scope |
| URL-based JD import (`link` source_type) | Adds URL fetching complexity | Future Scope |
| Email template customisation | MVP uses hardcoded/seeded templates | Post-MVP |
| Reminder emails (24h, 1h before interview) | Requires scheduling infrastructure | Future Scope |
| Calendar invite (.ics) attachments | Implementation detail for interview emails | Future Scope |
| Scheduling deadline notifications | Requires background scheduling | Future Scope |
| JD/application reprocessing | Recovery mechanism - HR can edit manually | Post-MVP |
| Job analytics endpoint | No requirement | Future Scope |
| User & company management UI | For MVP, seed initial data | Post-MVP |
| OAuth SSO | Not in requirements | Future Scope |
| WebSocket real-time updates | Polling is sufficient | Future Scope |
| Auto-scaling, monitoring | Operational - not MVP | Future Scope |

| Advanced notification types | Not in MVP scope | Future Scope |

---

## 5. User Roles (MVP)

| Role | How Created | Permissions |
|------|------------|------------|
| `super_admin` | Database seed | Full system access across all companies |
| `company_admin` | Database seed | Manage users within company, all company data |
| `hr_manager` | Registration + role assignment | Create/publish/close jobs, view all applicants, schedule interviews |
| `recruiter` | Registration + role assignment | Create/publish jobs, view own job applicants, schedule interviews |
| `candidate` | Registration or ghost user upgrade | Browse jobs, apply, view own application status |

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
8. JD status changes to `published` → appears on public job board

### Journey 2: Candidate Applies (Guest)

1. Candidate browses published jobs (no login required)
2. Selects a job → views details
3. Enters name, email, phone → requests upload URL → uploads resume PDF directly to S3
4. Submits form with `resume_key` → System creates ghost user + application record (status: `applied`)
5. Confirmation email sent to candidate (with opt-in link to create account)
6. Background: AI worker extracts resume data → matches against JD → scores candidate
7. Application status updated to `screened`

### Journey 3: Candidate Creates Account

1. Candidate clicks opt-in link from confirmation email (or registers directly)
2. Creates account with email and password
3. Ghost user upgraded to registered user - existing application(s) linked
4. Candidate can view application status from dashboard

### Journey 4: HR Reviews Candidates

1. HR opens applicant list for a JD
2. Sees ranked list sorted by AI matching score (default: descending)
3. Can sort by score, date, name, experience
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
- Malware scanning integration
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
| Malware detected | Handled by worker: fails task, status → `extraction_failed`, file deleted |
| Duplicate application (same email + same JD) | Reject with 409, clear error message |
| Network retry (duplicate submission) | `Idempotency-Key` header returns original response |
| LLM returns invalid JSON | Retry (treated as task failure). After max retries, DLQ + status = failed |
| Ghost user email matches existing user | Application linked to existing user automatically |
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
| AC-006 | Resume scoring → status = screened, score 0-10, matching_result populated | Phase 3 |
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

