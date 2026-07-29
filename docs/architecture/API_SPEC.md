# API Specification - AI-Powered Recruitment Platform

> **Source of Truth**: This document is the authoritative reference for all API contracts - routes, methods, roles, request/response schemas, status codes, error format, and query parameters.
>
> For architectural decisions explaining *why* the API is designed this way, see [SYSTEM_DESIGN.md](../architecture/SYSTEM_DESIGN.md) §5.

---

## Table of Contents

1. [Conventions](#1-conventions)
2. [Authentication Endpoints (MVP)](#2-authentication-endpoints-mvp)
3. [Job Description Endpoints (MVP)](#3-job-description-endpoints-mvp)
4. [Public Endpoints (MVP)](#4-public-endpoints-mvp)
5. [Application Endpoints (MVP)](#5-application-endpoints-mvp)
6. [Interview Scheduling Endpoints (MVP)](#6-interview-scheduling-endpoints-mvp)
7. [User & Company Management Endpoints (Post-MVP)](#7-user--company-management-endpoints-post-mvp)
8. [System Endpoints (MVP)](#8-system-endpoints-mvp)
9. [Phase 2 Endpoints](#9-phase-2-endpoints)

---

## 1. Conventions

### Base Path

All endpoints are prefixed with `/api/v1/`.

### Authentication

Unless explicitly marked as public, all endpoints require a valid JWT access token:
```
Authorization: Bearer <jwt_token>
```

Token lifecycle:
- Access token: 15-30 min TTL, stored in memory
- Refresh token: 7 day TTL, stored in httpOnly cookie
- On 401: client silently refreshes via `POST /auth/refresh`

### Error Response Format

All errors return a consistent JSON structure:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human-readable description",
    "details": [
      {
        "field": "title",
        "message": "Title is required"
      }
    ]
  }
}
```

### Common Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 201 | Created |
| 204 | No content (successful delete) |
| 400 | Bad request (malformed input) |
| 401 | Unauthorized (missing/invalid token) |
| 403 | Forbidden (insufficient role/permissions) |
| 404 | Resource not found |
| 409 | Conflict (e.g., duplicate application) |
| 422 | Unprocessable entity (validation error, infected file, publishing gate) |
| 429 | Rate limit exceeded |
| 500 | Internal server error |

### Pagination

All list endpoints support pagination:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | integer | 1 | Page number |
| `per_page` | integer | 20 | Results per page (max: 50) |

Response includes pagination metadata:
```json
{
  "page": 1,
  "per_page": 20,
  "total_pages": 5,
  "total_count": 95,
  "data": [...]
}
```

### Idempotency

Endpoints that create resources support the `Idempotency-Key` header:
```
Idempotency-Key: <unique-uuid>
```
If a request with the same key is received within 24 hours, the original response is returned without creating a duplicate.

### Rate Limiting

| Endpoint Group | Limit |
|----------------|-------|
| Public job application | 5 per hour per IP per JD |
| Auth login | 10 per 15 min per IP |
| AI-intensive endpoints | 20 per minute per authenticated user |
| General API | 300 per minute per authenticated user |

### File Uploads

File uploads use **pre-signed S3 URLs** to reduce backend load:
1. Client requests an upload URL via `POST /api/v1/jobs/upload-url` or `POST /api/v1/public/jobs/{id}/upload-url`.
2. Backend returns a pre-signed PUT URL and a unique `file_key`.
3. Client uploads the file directly to S3 via PUT.
4. Client submits the final form with the `file_key` in a standard JSON payload.
- Allowed types: PDF, DOCX
- Max size: 10MB
- Validated by MIME type AND magic byte signature
- Scanned for malware before storage

### File Downloads (Signed URLs)

All file downloads (resumes, JD documents) also use pre-signed URLs:
- Backend generates signed GET URL with 15-minute TTL
- Frontend uses the signed URL to download/display
- Object storage bucket remains private

---

## 2. Authentication Endpoints (MVP)

All auth endpoints are public (no token required) except where noted.

### POST /api/v1/auth/register
**Purpose**: Create a new user account
**Phase**: MVP
**Roles**: Public

```json
Request:
{
  "email": "hr@company.com",
  "password": "SecurePass123!",
  "first_name": "Jane",
  "last_name": "Doe",
  "company_id": "uuid"
}

Response 201:
{
  "id": "uuid",
  "email": "hr@company.com",
  "first_name": "Jane",
  "last_name": "Doe",
  "created_at": "2026-07-07T10:00:00Z"
}
```

### POST /api/v1/auth/login
**Purpose**: Authenticate and receive tokens
**Phase**: MVP
**Roles**: Public

```json
Request:
{
  "email": "hr@company.com",
  "password": "SecurePass123!"
}

Response 200:
{
  "access_token": "eyJhbG...",
  "token_type": "bearer",
  "expires_in": 1800,
  "user": {
    "id": "uuid",
    "email": "hr@company.com",
    "roles": ["hr_manager"],
    "company_id": "uuid"
  }
}
```
Refresh token set as httpOnly cookie.

### POST /api/v1/auth/refresh
**Purpose**: Issue new access token using refresh token
**Phase**: MVP
**Roles**: Authenticated (refresh token in cookie)

### POST /api/v1/auth/logout
**Purpose**: Revoke refresh token
**Phase**: MVP
**Roles**: Authenticated

### POST /api/v1/auth/forgot-password
**Purpose**: Request password reset email
**Phase**: MVP
**Roles**: Public

### POST /api/v1/auth/reset-password
**Purpose**: Reset password using token from email
**Phase**: MVP
**Roles**: Public (valid reset token required)

### GET /api/v1/auth/me
**Purpose**: Get current user profile
**Phase**: MVP
**Roles**: Authenticated

### PUT /api/v1/auth/me
**Purpose**: Update current user profile
**Phase**: MVP
**Roles**: Authenticated

---

## 3. Job Description Endpoints (MVP)

### Create Job Description & Upload URL

To upload a JD document, the client must first request a pre-signed upload URL, then submit the JD form with the resulting `document_key`.

#### 1. Request Upload URL

```json
POST /api/v1/jobs/upload-url
Authorization: Bearer <jwt>

Request:
{
  "content_type": "application/pdf",
  "file_name": "backend_jd.pdf"
}

Response 201:
{
  "upload_url": "https://s3.amazonaws.com/bucket/jds/uuid?signature...",
  "document_key": "jds/uuid",
  "expires_in": 900
}
```

#### 2. Create Job Description

### GET /api/v1/jobs
**Purpose**: List all jobs for the authenticated user's company
**Phase**: MVP
**Roles**: `hr_manager`, `recruiter`, `company_admin`, `super_admin`

**Query Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string | Filter by JD status |
| `page` | integer | Page number |
| `per_page` | integer | Results per page |

### POST /api/v1/jobs
**Purpose**: Create a new job description
**Phase**: MVP
**Roles**: `hr_manager`, `recruiter`, `company_admin`
**Headers**: `Idempotency-Key` supported
**Content-Type**: `application/json`

```json
Request:
{
  "title": "Senior Backend Engineer",
  "source_type": "document",
  "document_key": "jds/uuid",
  "status": "draft"
}

Response 201:
{
  "id": "uuid",
  "title": "Senior Backend Engineer",
  "status": "draft",
  "created_at": "2026-07-07T10:00:00Z",
  "message": "Job description created. AI processing will begin shortly."
}
```

### GET /api/v1/jobs/{id}
**Purpose**: Get job description details including extracted data
**Phase**: MVP
**Roles**: `hr_manager`, `recruiter`, `company_admin`, `super_admin`

### PUT /api/v1/jobs/{id}
**Purpose**: Update job description (edit title, description, extracted_data fields)
**Phase**: MVP
**Roles**: `hr_manager`, `recruiter`, `company_admin`

### DELETE /api/v1/jobs/{id}
**Purpose**: Delete job description (draft or closed only)
**Phase**: MVP
**Roles**: `hr_manager`, `company_admin`

### PATCH /api/v1/jobs/{id}/status
**Purpose**: Change JD status (publish, close, unpublish)
**Phase**: MVP
**Roles**: `hr_manager`, `recruiter`, `company_admin`

**Publishing gate**: Transition to `published` requires `title` and `extracted_data.required_skills` to be populated. Returns 422 if missing.

```json
Request:
{
  "status": "published"
}

Response 200:
{
  "id": "uuid",
  "status": "published",
  "published_at": "2026-07-07T12:00:00Z"
}
```

### POST /api/v1/jobs/{id}/reprocess
**Purpose**: Trigger re-extraction of AI data from the original document
**Phase**: Post-MVP
**Roles**: `hr_manager`, `company_admin`, `super_admin`

### GET /api/v1/jobs/{id}/applicants
**Purpose**: Get ranked applicant list for a job description
**Phase**: MVP
**Roles**: `hr_manager`, `recruiter`, `company_admin`, `super_admin`

**Query Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `sort` | string | Sort field: `score` (default), `date`, `name`, `experience` |
| `order` | string | Sort order: `desc` (default), `asc` |
| `status` | string | Filter by application status |
| `score_min` | float | Minimum matching score (0-10) |
| `score_max` | float | Maximum matching score (0-10) |
| `experience_min` | integer | Minimum years of experience |
| `experience_max` | integer | Maximum years of experience |
| `page` | integer | Page number |
| `per_page` | integer | Results per page (max: 50) |

```json
Response 200:
{
  "job_id": "uuid",
  "job_title": "Senior Backend Engineer",
  "total_applicants": 45,
  "page": 1,
  "per_page": 20,
  "total_pages": 3,
  "applicants": [
    {
      "id": "uuid",
      "candidate_first_name": "Alice",
      "candidate_last_name": "Smith",
      "candidate_email": "alice@example.com",
      "matching_score": 9.2,
      "years_of_experience": 7,
      "status": "screened",
      "applied_at": "2026-07-05T14:20:00Z",
      "matching_result": {
        "skills_match": { "score": 0.95 },
        "experience_match": { "score": 0.90 },
        "education_match": { "score": 0.88 },
        "overall_fit": { "recommendation": "strong_fit" }
      }
    }
  ]
}
```

### GET /api/v1/jobs/{id}/analytics
**Purpose**: Job statistics (application count, score distribution, etc.)
**Phase**: Future Scope
**Roles**: `hr_manager`, `company_admin`

---

## 4. Public Endpoints (MVP)

All public endpoints require NO authentication.

### Apply for Job & Upload URL

To apply with a resume, the client must first request a pre-signed upload URL, then submit the application with the resulting `resume_key`.

#### 1. Request Upload URL (Public)

```json
POST /api/v1/public/jobs/{job_id}/upload-url

Request:
{
  "content_type": "application/pdf",
  "file_name": "john_doe_resume.pdf"
}

Response 201:
{
  "upload_url": "https://s3.amazonaws.com/bucket/resumes/uuid?signature...",
  "resume_key": "resumes/uuid",
  "expires_in": 900
}
```

#### 2. Submit Application

### GET /api/v1/public/jobs
**Purpose**: Browse published jobs
**Phase**: MVP
**Roles**: Public (no auth)

### GET /api/v1/public/jobs/{id}
**Purpose**: View published job details
**Phase**: MVP
**Roles**: Public (no auth)

### POST /api/v1/public/jobs/{id}/apply
**Purpose**: Submit a job application (guest or authenticated)
**Phase**: MVP
**Roles**: Public (no auth required)
**Headers**: `Idempotency-Key` supported
**Content-Type**: `application/json`

```json
POST /api/v1/public/jobs/{job_id}/apply
Idempotency-Key: <unique-uuid>

Request:
{
  "candidate_first_name": "John",
  "candidate_last_name": "Doe",
  "candidate_email": "john@example.com",
  "candidate_phone": "+1234567890",
  "resume_key": "resumes/uuid",
  "cover_letter": "I am excited to apply..."
}

Response 201:
{
  "id": "uuid",
  "job_id": "uuid",
  "status": "applied",
  "message": "Application submitted. We'll review your profile shortly.",
  "applied_at": "2026-07-07T11:30:00Z"
}
```

**Duplicate check**: Returns 409 if the same email already has an application for this JD.

---

## 5. Application Endpoints (MVP)

### GET /api/v1/applications
**Purpose**: List all applications (HR view, company-scoped)
**Phase**: MVP
**Roles**: `hr_manager`, `recruiter`, `company_admin`, `super_admin`

### GET /api/v1/applications/{id}
**Purpose**: Get full application details including AI scoring breakdown, resume download (signed URL)
**Phase**: MVP
**Roles**: `hr_manager`, `recruiter`, `company_admin`, `super_admin`, `candidate` (own only)

### PATCH /api/v1/applications/{id}/status
**Purpose**: Update application status (shortlist, reject)
**Phase**: MVP
**Roles**: `hr_manager`, `recruiter`, `company_admin`

**Valid transitions**:
- `screened` → `shortlisted`
- `screened` → `rejected`
- `shortlisted` → `rejected`
- `shortlisted` → `interview_scheduled` (triggers scheduling flow)

```json
Request:
{
  "status": "shortlisted"
}
```

### PATCH /api/v1/applications/bulk/status
**Purpose**: Bulk update application status (shortlist/reject multiple)
**Phase**: Future Scope
**Roles**: `hr_manager`, `company_admin`

### POST /api/v1/applications/{id}/reprocess
**Purpose**: Trigger re-parsing and re-scoring
**Phase**: Post-MVP
**Roles**: `hr_manager`, `company_admin`, `super_admin`

---

## 6. Interview Scheduling Endpoints (MVP)

### POST /api/v1/interviews
**Purpose**: Create interview invitation (Option A: direct invite, or Option B: self-scheduling)
**Phase**: MVP
**Roles**: `hr_manager`, `recruiter`, `company_admin`

**Option A - Direct Invite**:
```json
Request:
{
  "application_id": "uuid",
  "interview_type": "initial",
  "meeting_link": "https://meet.google.com/abc",
  "scheduled_at": "2026-07-15T10:00:00Z"
}

Response 201:
{
  "id": "uuid",
  "status": "scheduled",
  "scheduled_at": "2026-07-15T10:00:00Z"
}
```

**Option B - Self-Scheduling**:
```json
Request:
{
  "application_id": "uuid",
  "interview_type": "initial",
  "time_slot_options": [
    "2026-07-15T10:00:00Z",
    "2026-07-16T14:00:00Z",
    "2026-07-17T11:00:00Z"
  ],
  "slot_deadline": "2026-07-14T10:00:00Z"
}

Response 201:
{
  "id": "uuid",
  "status": "pending",
  "scheduling_token": "abc123",
  "scheduling_url": "/interviews/schedule/abc123"
}
```

### GET /api/v1/interviews/{id}
**Purpose**: Get interview details
**Phase**: MVP
**Roles**: `hr_manager`, `recruiter`, `company_admin`, `super_admin`

### PUT /api/v1/interviews/{id}
**Purpose**: Update interview (change time, meeting link)
**Phase**: MVP
**Roles**: `hr_manager`, `recruiter`, `company_admin`

### DELETE /api/v1/interviews/{id}
**Purpose**: Cancel interview
**Phase**: MVP
**Roles**: `hr_manager`, `company_admin`

### GET /api/v1/interviews/schedule/{token}
**Purpose**: Public page - candidate views available time slots
**Phase**: MVP
**Roles**: Public (valid scheduling token required)

### POST /api/v1/interviews/schedule/{token}
**Purpose**: Candidate selects a time slot
**Phase**: MVP
**Roles**: Public (valid scheduling token required)

```json
Request:
{
  "selected_slot": "2026-07-16T14:00:00Z"
}

Response 200:
{
  "status": "scheduled",
  "scheduled_at": "2026-07-16T14:00:00Z",
  "message": "Interview scheduled. Confirmation emails sent."
}
```

---

## 7. User & Company Management Endpoints (Post-MVP)

These endpoints consolidate administrative operations under standard resource URLs. Access is controlled by RBAC - there is no separate `/admin/` namespace.

### GET /api/v1/users
**Purpose**: List users
**Phase**: Post-MVP
**Roles**: `super_admin` (all), `company_admin` (own company)

### POST /api/v1/users
**Purpose**: Create user
**Phase**: Post-MVP
**Roles**: `super_admin` (any company), `company_admin` (own company)

### PUT /api/v1/users/{id}
**Purpose**: Update user (role-scoped)
**Phase**: Post-MVP
**Roles**: `super_admin`, `company_admin` (own company)

### DELETE /api/v1/users/{id}
**Purpose**: Deactivate user (role-scoped)
**Phase**: Post-MVP
**Roles**: `super_admin`, `company_admin` (own company)

### GET /api/v1/companies
**Purpose**: List companies
**Phase**: Post-MVP
**Roles**: `super_admin` only

### POST /api/v1/companies
**Purpose**: Create company
**Phase**: Post-MVP
**Roles**: `super_admin` only

### GET /api/v1/roles
**Purpose**: List roles
**Phase**: Post-MVP
**Roles**: `super_admin` (all), `company_admin` (assignable roles)

### POST /api/v1/roles
**Purpose**: Create/update roles
**Phase**: Post-MVP
**Roles**: `super_admin` only

---

## 8. System Endpoints (MVP)

### GET /api/v1/system/health
**Purpose**: System health check
**Phase**: MVP
**Roles**: `super_admin` only


