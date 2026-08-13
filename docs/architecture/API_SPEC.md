# EZScreen REST & Inter-Service API Specification

> **Version**: 1.0.0  
> **Production Gateway Base URL**: `https://api.ezscreen.io/api/v1`  
> **Local Dev Gateway Base URL**: `http://localhost:8000/api/v1`  
> **Internal Service Base URLs**: `http://parsing-matching:8001/internal/v1`, `http://ai-screening:8002/internal/v1`  
> **Format**: JSON (`Content-Type: application/json`)  
> **Auth**: Bearer Token (`Authorization: Bearer <jwt>`)

---

## 1. System Roles & Multi-Tenancy Architecture

| Role | Scope | Key Capabilities & Provisioning Rules |
| :--- | :--- | :--- |
| **`super_admin`** | Platform Scope (`organization_id NULL`) | Platform owner. Creates Organizations (`organizations`); provisions `organization_admin` and `hr` users. |
| **`organization_admin`** | Organization Scope (`organization_id NOT NULL`) | Organization Administrator. Bound strictly to one organization. Provisions secondary `organization_admin` and `hr` users within their organization. |
| **`hr`** | Organization Scope (`organization_id NOT NULL`) | Operational HR user. Bound strictly to one organization. Parses & publishes JDs, views applicant scores, schedules AI interview sessions, dispatches meeting bots, and reviews screening reports. |
| **`candidate`** | Candidate Scope (`organization_id NULL`) | Guest / Candidate applicant. Browses published jobs via organization subdomain (`{org}.ezscreen.io`) and submits resume applications. |

---

## 2. Modular Architecture & Inter-Service API Boundaries

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
**Tag**: `Authentication`  
**Summary**: Authenticate user & receive JWT token  
**Operation ID**: `loginUser`  
**Roles**: Public  

```json
Request:
{
  "headers": {
    "Content-Type": "application/json"
  },
  "body": {
    "email": "admin@acme.com",
    "password": "SecurePassword123!"
  }
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
    "phone": "+1-555-0199",
    "role": "organization_admin",
    "status": "active",
    "organization_id": "987e6543-e89b-12d3-a456-426614174000"
  }
}
```

#### POST /api/v1/auth/org/login
**Tag**: `Authentication`  
**Summary**: Authenticate Organization Admin or HR for workspace access  
**Operation ID**: `orgWorkspaceLogin`  
**Roles**: Public  

Organization workspace portal login. Rejects `super_admin` / `candidate`, and rejects users whose organization is missing or suspended. Same token + refresh-cookie response shape as `/auth/login`.

```json
Request:
{
  "headers": {
    "Content-Type": "application/json"
  },
  "body": {
    "email": "admin@acme.com",
    "password": "SecurePassword123!"
  }
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
      "phone": "+1-555-0199",
      "role": "organization_admin",
      "status": "active",
      "organization_id": "987e6543-e89b-12d3-a456-426614174000"
    }
}

Response 401:
{ "detail": "Invalid email or password" }

Response 403:
{ "detail": "Organization workspace access only" }
```

#### GET /api/v1/auth/org/check
**Tag**: `Authentication`  
**Summary**: Verify Organization Admin or HR token and role  
**Operation ID**: `orgWorkspaceCheck`  
**Roles**: `organization_admin`, `hr`

```json
Response 200:
{
  "message": "Organization workspace access confirmed"
}
```

#### POST /api/v1/auth/logout
**Tag**: `Authentication`  
**Summary**: Revoke session token and logout  
**Operation ID**: `logoutUser`  
**Roles**: Authenticated  

```json
Request:
{
  "headers": {
    "Authorization": "Bearer <jwt_token>"
  },
  "body": {}
}

Response 200:
{
  "message": "Successfully logged out"
}
```

#### POST /api/v1/auth/forgot-password
**Tag**: `Authentication`  
**Summary**: Request password reset link via email  
**Operation ID**: `forgotPassword`  
**Roles**: Public  

```json
Request:
{
  "headers": {
    "Content-Type": "application/json"
  },
  "body": {
    "email": "hr.jane@acme.com"
  }
}

Response 200:
{
  "message": "Password reset instructions sent to your email"
}
```

#### POST /api/v1/auth/reset-password
**Tag**: `Authentication`  
**Summary**: Reset password using email token  
**Operation ID**: `resetPassword`  
**Roles**: Public (valid token required)  

```json
Request:
{
  "headers": {
    "Content-Type": "application/json"
  },
  "body": {
    "token": "reset_token_abc123xyz",
    "new_password": "NewSecurePassword456!"
  }
}

Response 200:
{
  "message": "Password successfully reset"
}
```

#### GET /api/v1/auth/me
**Tag**: `Authentication`  
**Summary**: Retrieve current authenticated user profile  
**Operation ID**: `getCurrentUser`  
**Roles**: Authenticated  

```json
Request:
{
  "headers": {
    "Authorization": "Bearer <jwt_token>"
  },
  "body": {}
}

Response 200:
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "organization_id": "987e6543-e89b-12d3-a456-426614174000",
  "role": "organization_admin",
  "email": "admin@acme.com",
  "first_name": "Alice",
  "last_name": "Admin",
  "phone": "+1-555-0199",
  "status": "active"
}
```

---

### B. Organization & User Provisioning Endpoints

#### POST /api/v1/organizations
**Tag**: `Organizations & User Provisioning`  
**Summary**: Super Admin creates a new organization  
**Operation ID**: `createOrganization`  
**Roles**: `super_admin`  

```json
Request:
{
  "headers": {
    "Authorization": "Bearer <super_admin_jwt>",
    "Content-Type": "application/json"
  },
  "body": {
    "name": "Acme Corporation",
    "domain": "acme",
    "logo_url": "https://acme.com/logo.png"
  }
}

Response 201:
{
  "id": "987e6543-e89b-12d3-a456-426614174000",
  "name": "Acme Corporation",
  "domain": "acme",
  "logo_url": "https://acme.com/logo.png",
  "is_active": true
}
```

#### GET /api/v1/organizations
**Tag**: `Organizations & User Provisioning`  
**Summary**: List all organizations (Super Admin only)  
**Operation ID**: `listOrganizations`  
**Roles**: `super_admin`  

```json
Request:
{
  "headers": {
    "Authorization": "Bearer <super_admin_jwt>"
  },
  "query": {
    "page": 1,
    "limit": 20
  },
  "body": {}
}

Response 200:
[
  {
    "id": "987e6543-e89b-12d3-a456-426614174000",
    "name": "Acme Corporation",
    "domain": "acme",
    "logo_url": "https://acme.com/logo.png",
    "is_active": true
  }
]
```

#### GET /api/v1/organizations/{id}
**Tag**: `Organizations & User Provisioning`  
**Summary**: View organization details  
**Operation ID**: `getOrganization`  
**Roles**: `super_admin`, `organization_admin` (own org)  

```json
Request:
{
  "headers": {
    "Authorization": "Bearer <jwt_token>"
  },
  "path": {
    "id": "987e6543-e89b-12d3-a456-426614174000"
  },
  "body": {}
}

Response 200:
{
  "id": "987e6543-e89b-12d3-a456-426614174000",
  "name": "Acme Corporation",
  "domain": "acme",
  "logo_url": "https://acme.com/logo.png",
  "is_active": true
}
```

#### PUT /api/v1/organizations/{id}
**Tag**: `Organizations & User Provisioning`  
**Summary**: Update organization details  
**Operation ID**: `updateOrganization`  
**Roles**: `super_admin`, `organization_admin` (own org)  

```json
Request:
{
  "headers": {
    "Authorization": "Bearer <jwt_token>",
    "Content-Type": "application/json"
  },
  "path": {
    "id": "987e6543-e89b-12d3-a456-426614174000"
  },
  "body": {
    "name": "Acme Global Inc.",
    "domain": "acmeglobal",
    "logo_url": "https://acmeglobal.com/new_logo.png"
  }
}

Response 200:
{
  "id": "987e6543-e89b-12d3-a456-426614174000",
  "name": "Acme Global Inc.",
  "domain": "acmeglobal",
  "logo_url": "https://acmeglobal.com/new_logo.png",
  "is_active": true
}
```

#### DELETE /api/v1/organizations/{id}
**Tag**: `Organizations & User Provisioning`  
**Summary**: Soft delete / deactivate organization  
**Operation ID**: `deleteOrganization`  
**Roles**: `super_admin`  

```json
Request:
{
  "headers": {
    "Authorization": "Bearer <super_admin_jwt>"
  },
  "path": {
    "id": "987e6543-e89b-12d3-a456-426614174000"
  },
  "body": {}
}

Response 200:
{
  "id": "987e6543-e89b-12d3-a456-426614174000",
  "is_active": false,
  "message": "Organization deactivated"
}
```

#### GET /api/v1/organizations/{id}/users
**Tag**: `Organizations & User Provisioning`  
**Summary**: List users belonging to an organization  
**Operation ID**: `listOrgUsers`  
**Roles**: `super_admin`, `organization_admin` (own org)  

```json
Request:
{
  "headers": {
    "Authorization": "Bearer <jwt_token>"
  },
  "path": {
    "id": "987e6543-e89b-12d3-a456-426614174000"
  },
  "body": {}
}

Response 200:
[
  {
    "id": "333e4567-e89b-12d3-a456-426614174000",
    "organization_id": "987e6543-e89b-12d3-a456-426614174000",
    "role": "hr",
    "email": "hr.jane@acme.com",
    "first_name": "Jane",
    "last_name": "Smith",
    "phone": "+1-555-0199",
    "status": "active"
  }
]
```

#### POST /api/v1/organizations/{id}/users
**Tag**: `Organizations & User Provisioning`  
**Summary**: Unified endpoint to provision Organization Admin or HR users  
**Operation ID**: `provisionOrgUser`  
**Roles**: `super_admin`, `organization_admin` (own org)  

```json
Request:
{
  "headers": {
    "Authorization": "Bearer <jwt_token>",
    "Content-Type": "application/json"
  },
  "path": {
    "id": "987e6543-e89b-12d3-a456-426614174000"
  },
  "body": {
    "email": "hr.jane@acme.com",
    "password": "SecurePassword123!",
    "first_name": "Jane",
    "last_name": "Smith",
    "phone": "+1-555-0199",
    "role": "hr"
  }
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
  "status": "active"
}
```

---

### C. Job Description Endpoints (Direct Parsing & Unified Update)

#### POST /api/v1/jobs/parse
**Tag**: `Job Descriptions`  
**Summary**: Direct in-memory parsing of raw JD file or text  
**Operation ID**: `parseJobDescription`  
**Roles**: `hr`, `organization_admin`, `super_admin`  

```json
Request:
{
  "headers": {
    "Authorization": "Bearer <hr_jwt>",
    "Content-Type": "application/json"
  },
  "body": {
    "raw_text": "Senior Java Developer with 3-5 years experience in Spring Boot, PostgreSQL, and Docker."
  }
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
**Tag**: `Job Descriptions`  
**Summary**: Save & publish job description record  
**Operation ID**: `createJobDescription`  
**Roles**: `hr`, `organization_admin`, `super_admin`  

```json
Request:
{
  "headers": {
    "Authorization": "Bearer <hr_jwt>",
    "Content-Type": "application/json"
  },
  "body": {
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
}

Response 201:
{
  "id": "444e4567-e89b-12d3-a456-426614174000",
  "organization_id": "987e6543-e89b-12d3-a456-426614174000",
  "created_by": "333e4567-e89b-12d3-a456-426614174000",
  "title": "Senior Java Developer",
  "description": "Looking for a Senior Java Developer...",
  "job_type": "full_time",
  "work_type": "hybrid",
  "location": "Bangalore",
  "experience_min": 3,
  "experience_max": 5,
  "skills": "Java, Spring Boot, PostgreSQL, Docker",
  "status": "published",
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

#### GET /api/v1/jobs
**Tag**: `Job Descriptions`  
**Summary**: List job descriptions for organization  
**Operation ID**: `listJobs`  
**Roles**: `hr`, `organization_admin`, `super_admin`  

```json
Request:
{
  "headers": {
    "Authorization": "Bearer <hr_jwt>"
  },
  "query": {
    "status": "published",
    "page": 1,
    "limit": 20
  },
  "body": {}
}

Response 200:
[
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
    "skills": "Java, Spring Boot, PostgreSQL",
    "status": "published"
  }
]
```

#### GET /api/v1/jobs/{id}
**Tag**: `Job Descriptions`  
**Summary**: View job description details  
**Operation ID**: `getJob`  
**Roles**: `hr`, `organization_admin`, `super_admin`  

```json
Request:
{
  "headers": {
    "Authorization": "Bearer <hr_jwt>"
  },
  "path": {
    "id": "444e4567-e89b-12d3-a456-426614174000"
  },
  "body": {}
}

Response 200:
{
  "id": "444e4567-e89b-12d3-a456-426614174000",
  "organization_id": "987e6543-e89b-12d3-a456-426614174000",
  "created_by": "333e4567-e89b-12d3-a456-426614174000",
  "title": "Senior Java Developer",
  "description": "Looking for a Senior Java Developer...",
  "job_type": "full_time",
  "work_type": "hybrid",
  "location": "Bangalore",
  "experience_min": 3,
  "experience_max": 5,
  "skills": "Java, Spring Boot, PostgreSQL, Docker",
  "status": "published",
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

#### PUT /api/v1/jobs/{id}
**Tag**: `Job Descriptions`  
**Summary**: Unified endpoint to update job description fields, parsed_jd requirements, and/or status  
**Operation ID**: `updateJob`  
**Roles**: `hr`, `organization_admin`, `super_admin`  

```json
Request:
{
  "headers": {
    "Authorization": "Bearer <hr_jwt>",
    "Content-Type": "application/json"
  },
  "path": {
    "id": "444e4567-e89b-12d3-a456-426614174000"
  },
  "body": {
    "title": "Lead Java Backend Engineer",
    "description": "Updated job description text...",
    "job_type": "full_time",
    "work_type": "remote",
    "location": "Remote - India",
    "experience_min": 5,
    "experience_max": 8,
    "skills": "Java, Spring Boot, PostgreSQL, Kafka, AWS",
    "status": "closed"
  }
}

Response 200:
{
  "id": "444e4567-e89b-12d3-a456-426614174000",
  "title": "Lead Java Backend Engineer",
  "status": "closed"
}
```

---

### D. Public Candidate Endpoints (Subdomain Scoped)

#### GET /api/v1/public/jobs
**Tag**: `Public Candidate Portal`  
**Summary**: Candidate browse published jobs for organization subdomain  
**Operation ID**: `listPublicJobs`  
**Roles**: `candidate` (Public)  

```json
Request:
{
  "headers": {
    "Host": "acme.ezscreen.io"
  },
  "query": {
    "org_subdomain": "acme"
  },
  "body": {}
}

Response 200:
[
  {
    "id": "444e4567-e89b-12d3-a456-426614174000",
    "title": "Senior Java Developer",
    "job_type": "full_time",
    "work_type": "hybrid",
    "location": "Bangalore",
    "experience_min": 3,
    "experience_max": 5,
    "skills": "Java, Spring Boot, PostgreSQL"
  }
]
```

#### GET /api/v1/public/jobs/{id}
**Tag**: `Public Candidate Portal`  
**Summary**: Candidate view published job details  
**Operation ID**: `getPublicJob`  
**Roles**: `candidate` (Public)  

```json
Request:
{
  "headers": {
    "Host": "acme.ezscreen.io"
  },
  "path": {
    "id": "444e4567-e89b-12d3-a456-426614174000"
  },
  "body": {}
}

Response 200:
{
  "id": "444e4567-e89b-12d3-a456-426614174000",
  "title": "Senior Java Developer",
  "description": "Looking for a Senior Java Developer...",
  "job_type": "full_time",
  "work_type": "hybrid",
  "location": "Bangalore",
  "experience_min": 3,
  "experience_max": 5,
  "skills": "Java, Spring Boot, PostgreSQL"
}
```

#### POST /api/v1/public/jobs/{id}/apply
**Tag**: `Public Candidate Portal`  
**Summary**: Candidate submit application with resume file  
**Operation ID**: `applyJob`  
**Roles**: `candidate` (Public)  

```json
Request:
{
  "headers": {
    "Host": "acme.ezscreen.io",
    "Content-Type": "multipart/form-data"
  },
  "path": {
    "id": "444e4567-e89b-12d3-a456-426614174000"
  },
  "form_fields": {
    "email": "john.doe@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "phone": "+1-555-0188"
  },
  "file": {
    "resume": "<binary_pdf_docx>"
  }
}

Response 201:
{
  "id": "555e4567-e89b-12d3-a456-426614174000",
  "job_description_id": "444e4567-e89b-12d3-a456-426614174000",
  "candidate_id": "777e4567-e89b-12d3-a456-426614174000",
  "status": "applied",
  "resume_score": 85.0,
  "candidate_yoe": 5.0
}
```

---

### E. Candidate Visibility & Application Management Endpoints

#### GET /api/v1/jobs/{id}/applicants
**Tag**: `Candidate Applications`  
**Summary**: HR view candidate applicants for a job sorted by score  
**Operation ID**: `listApplicants`  
**Roles**: `hr`, `organization_admin`, `super_admin`  

```json
Request:
{
  "headers": {
    "Authorization": "Bearer <hr_jwt>"
  },
  "path": {
    "id": "444e4567-e89b-12d3-a456-426614174000"
  },
  "query": {
    "sort": "resume_score_desc",
    "page": 1,
    "limit": 50
  },
  "body": {}
}

Response 200:
[
  {
    "id": "555e4567-e89b-12d3-a456-426614174000",
    "job_description_id": "444e4567-e89b-12d3-a456-426614174000",
    "candidate_id": "777e4567-e89b-12d3-a456-426614174000",
    "status": "applied",
    "candidate_yoe": 5.0,
    "resume_score": 85.0
  }
]
```

#### GET /api/v1/applications/{id}
**Tag**: `Candidate Applications`  
**Summary**: View application details with parsed resume & match matrix  
**Operation ID**: `getApplication`  
**Roles**: `hr`, `organization_admin`, `super_admin`  

```json
Request:
{
  "headers": {
    "Authorization": "Bearer <hr_jwt>"
  },
  "path": {
    "id": "555e4567-e89b-12d3-a456-426614174000"
  },
  "body": {}
}

Response 200:
{
  "id": "555e4567-e89b-12d3-a456-426614174000",
  "job_description_id": "444e4567-e89b-12d3-a456-426614174000",
  "candidate_id": "777e4567-e89b-12d3-a456-426614174000",
  "status": "applied",
  "candidate_yoe": 5.0,
  "resume_score": 85.0,
  "parsed_resume": {
    "candidate_name": "John Doe",
    "email": "john.doe@example.com",
    "skills": ["Java", "Spring Boot", "PostgreSQL"]
  },
  "job_fit_analysis": {
    "overall_score": 85,
    "matched_skills": ["Java", "Spring Boot"]
  }
}
```

#### PATCH /api/v1/applications/{id}/status
**Tag**: `Candidate Applications`  
**Summary**: Update candidate application status  
**Operation ID**: `updateApplicationStatus`  
**Roles**: `hr`, `organization_admin`, `super_admin`  

```json
Request:
{
  "headers": {
    "Authorization": "Bearer <hr_jwt>",
    "Content-Type": "application/json"
  },
  "path": {
    "id": "555e4567-e89b-12d3-a456-426614174000"
  },
  "body": {
    "status": "interview_scheduled"
  }
}

Response 200:
{
  "id": "555e4567-e89b-12d3-a456-426614174000",
  "status": "interview_scheduled"
}
```

---

### F. Interview Sessions, Attendee Bot Dispatch & Analysis Endpoints

#### POST /api/v1/interview-sessions
**Tag**: `Interview Sessions & Analysis`  
**Summary**: Schedule interview session and generate static questions  
**Operation ID**: `scheduleInterviewSession`  
**Roles**: `hr`, `organization_admin`, `super_admin`  

```json
Request:
{
  "headers": {
    "Authorization": "Bearer <hr_jwt>",
    "Content-Type": "application/json"
  },
  "body": {
    "application_id": "555e4567-e89b-12d3-a456-426614174000",
    "interview_type": "screening_ai",
    "scheduled_at": "2026-08-05T10:00:00Z",
    "comment": "Initial AI screening call",
    "interview_metadata": {
      "gmeet_link": "https://meet.google.com/abc-defg-hij",
      "time_zone": "Asia/Kolkata"
    }
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
      "question": "How have you handled container orchestration using Kubernetes in production?"
    }
  ]
}
```

#### POST /api/v1/interview-sessions/{id}/dispatch-bot
**Tag**: `Interview Sessions & Analysis`  
**Summary**: Dispatch Attendee.dev meeting bot to Google Meet URL  
**Operation ID**: `dispatchMeetingBot`  
**Roles**: `hr`, `organization_admin`, `super_admin`  

```json
Request:
{
  "headers": {
    "Authorization": "Bearer <hr_jwt>",
    "Content-Type": "application/json"
  },
  "path": {
    "id": "666e4567-e89b-12d3-a456-426614174000"
  },
  "body": {
    "gmeet_link": "https://meet.google.com/abc-defg-hij",
    "bot_name": "EZScreen Screening Assistant"
  }
}

Response 200:
{
  "interview_session_id": "666e4567-e89b-12d3-a456-426614174000",
  "bot_id": "bot_99182371a",
  "status": "scheduled",
  "gmeet_link": "https://meet.google.com/abc-defg-hij",
  "dispatched_at": "2026-08-05T09:55:00Z",
  "message": "Attendee bot successfully scheduled for call entry"
}
```

#### GET /api/v1/interview-sessions/{id}
**Tag**: `Interview Sessions & Analysis`  
**Summary**: View interview session details  
**Operation ID**: `getInterviewSession`  
**Roles**: `hr`, `organization_admin`, `super_admin`  

```json
Request:
{
  "headers": {
    "Authorization": "Bearer <hr_jwt>"
  },
  "path": {
    "id": "666e4567-e89b-12d3-a456-426614174000"
  },
  "body": {}
}

Response 200:
{
  "id": "666e4567-e89b-12d3-a456-426614174000",
  "application_id": "555e4567-e89b-12d3-a456-426614174000",
  "scheduled_by": "333e4567-e89b-12d3-a456-426614174000",
  "interview_type": "screening_ai",
  "status": "scheduled",
  "scheduled_at": "2026-08-05T10:00:00Z"
}
```

#### PATCH /api/v1/interview-sessions/{id}/status
**Tag**: `Interview Sessions & Analysis`  
**Summary**: Update interview session status  
**Operation ID**: `updateInterviewSessionStatus`  
**Roles**: `hr`, `organization_admin`, `super_admin`  

```json
Request:
{
  "headers": {
    "Authorization": "Bearer <hr_jwt>",
    "Content-Type": "application/json"
  },
  "path": {
    "id": "666e4567-e89b-12d3-a456-426614174000"
  },
  "body": {
    "status": "completed"
  }
}

Response 200:
{
  "id": "666e4567-e89b-12d3-a456-426614174000",
  "status": "completed"
}
```

#### GET /api/v1/interview-sessions/{id}/analysis
**Tag**: `Interview Sessions & Analysis`  
**Summary**: View AI transcript screening report for interview session  
**Operation ID**: `getInterviewAnalysis`  
**Roles**: `hr`, `organization_admin`, `super_admin`  

```json
Request:
{
  "headers": {
    "Authorization": "Bearer <hr_jwt>"
  },
  "path": {
    "id": "666e4567-e89b-12d3-a456-426614174000"
  },
  "body": {}
}

Response 200:
{
  "id": "888e4567-e89b-12d3-a456-426614174000",
  "interview_session_id": "666e4567-e89b-12d3-a456-426614174000",
  "application_id": "555e4567-e89b-12d3-a456-426614174000",
  "interview_type": "screening_ai",
  "recording_url": "https://media.attendee.dev/recordings/rec_99182.mp3",
  "analysis_result": {
    "overall_feedback": "Candidate demonstrated strong backend development skills.",
    "final_recommendation": "Shortlist for L1"
  },
  "question_answer": [
    {
      "question_id": 1,
      "score": 9
    }
  ]
}
```

#### POST /api/v1/webhooks/attendee
**Tag**: `Webhooks`  
**Summary**: Attendee.dev meeting bot webhook ingestion  
**Operation ID**: `handleAttendeeWebhook`  
**Roles**: Public (Webhook Signature Validated)  

```json
Request:
{
  "headers": {
    "Content-Type": "application/json"
  },
  "body": {
    "event": "bot.completed",
    "bot_id": "bot_99182371a",
    "session_id": "666e4567-e89b-12d3-a456-426614174000",
    "recording_url": "https://media.attendee.dev/recordings/rec_99182.mp3",
    "transcript": []
  }
}

Response 200:
{
  "status": "success",
  "event_processed": "bot.completed"
}
```

---

## 4. Internal Service APIs (`Internal Service`)

### A. Parsing & Matching Microservice (`services/parsing-matching`)
* **Base URL**: `http://parsing-matching:8001/internal/v1`

#### POST /internal/v1/parse/jd
**Tag**: `Internal Service`  
**Summary**: Internal JD parsing engine (services/parsing-matching)  
**Operation ID**: `internalParseJD`  

```json
Request:
{
  "headers": {
    "Content-Type": "application/json"
  },
  "body": {
    "raw_text": "Senior Java Developer..."
  }
}

Response 200:
{
  "title": "Senior Java Developer",
  "parsed_jd": {}
}
```

#### POST /internal/v1/parse/resume
**Tag**: `Internal Service`  
**Summary**: Internal resume parsing engine (services/parsing-matching)  
**Operation ID**: `internalParseResume`  

```json
Request:
{
  "headers": {
    "Content-Type": "application/json"
  },
  "body": {
    "resume_base64": "<base64>",
    "file_name": "resume.pdf"
  }
}

Response 200:
{
  "parsed_resume": {}
}
```

#### POST /internal/v1/match/resume-jd
**Tag**: `Internal Service`  
**Summary**: Internal candidate-JD matching score calculation (services/parsing-matching)  
**Operation ID**: `internalMatchResumeJD`  

```json
Request:
{
  "headers": {
    "Content-Type": "application/json"
  },
  "body": {
    "parsed_jd": {},
    "parsed_resume": {}
  }
}

Response 200:
{
  "resume_score": 85.0,
  "job_fit_analysis": {}
}
```

---

### B. AI Screening Microservice (`services/ai-screening`)
* **Base URL**: `http://ai-screening:8002/internal/v1`

#### POST /internal/v1/screening/questions/generate
**Tag**: `Internal Service`  
**Summary**: Internal session question generation (services/ai-screening)  
**Operation ID**: `internalGenerateQuestions`  

```json
Request:
{
  "headers": {
    "Content-Type": "application/json"
  },
  "body": {
    "parsed_jd": {},
    "parsed_resume": {}
  }
}

Response 200:
{
  "generated_questions": []
}
```

#### POST /internal/v1/screening/analysis/evaluate
**Tag**: `Internal Service`  
**Summary**: Internal transcript screening evaluation (services/ai-screening)  
**Operation ID**: `internalEvaluateTranscript`  

```json
Request:
{
  "headers": {
    "Content-Type": "application/json"
  },
  "body": {
    "transcript": [],
    "generated_questions": []
  }
}

Response 200:
{
  "analysis_result": {},
  "question_answer": []
}
```
