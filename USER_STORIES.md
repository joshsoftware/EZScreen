# Consolidated User Stories - EZScreen Platform

This document serves as the single source of truth for developer user stories on the EZScreen platform. It aligns the [AI-Powered Screening Requirements](../requirements/AI_SCREENING_REQUIREMENTS.md), the [MVP Technical Document](../mvp/MVP.md), the [System Design](../architecture/SYSTEM_DESIGN.md), and the [Attendee Bot Integration](../integrations/ATTENDEE_INTEGRATION.md) to reconcile scope differences, outline clear acceptance criteria, and classify tasks into MVP vs. Post-MVP phases.

---

## Epic 1: Multi-Tenant Authentication & Access Control (Auth)

### US-1.1: HR User Registration & Login
* **User Story:** As an HR User / Recruiter, I want to register for an account and log in securely using JWT authentication so that I can access my company's workspace and keep recruitment data secure.
* **Acceptance Criteria:**
  - HR registers by providing Email, Password, First Name, Last Name, and Company Name.
  - Login returns a stateless JWT Access Token (15–30 min TTL) in memory and a HTTP-only Refresh Token cookie (7-day TTL).
  - Invalid login credentials return a clear `401 Unauthorized` error.
  - A password reset workflow via secure email links works end-to-end.
* **Scope / Phase:** MVP (Phase 1: Foundation)

### US-1.2: Role-Based Access Control & Company Isolation
* **User Story:** As an HR Manager / Org Admin, I want all system operations to be restricted to my company's domain so that I cannot view or modify candidate applications, jobs, or interviews belonging to other organizations.
* **Acceptance Criteria:**
  - System middleware validates the authenticated user's `company_id` on all protected endpoints.
  - Querying, updating, or deleting records belonging to another company returns a strict `403 Forbidden`.
  - The `super_admin` role operates globally (e.g., seeding companies, global user roles) without organization constraints.
* **Scope / Phase:** MVP (Phase 1: Foundation)

### US-1.3: CLI-Based Organization & Admin Seeding
* **User Story:** As a Developer / System Administrator, I want to create organizations and initial company admins using a database seed script so that company workspaces can be initialized without requiring a management UI.
* **Acceptance Criteria:**
  - Running a seed CLI command populates the database with default roles (`super_admin`, `organization_admin`, `hr`).
  - Creates at least one default active Organization record.
  - Creates one default active User with the `organization_admin` role linked to that organization.
* **Scope / Phase:** MVP (Phase 1: Foundation)

### US-1.4: Super Admin Organization Creation UI
* **User Story:** As a Super Admin, I want an admin dashboard UI to create and configure new client organizations on the platform so that I can onboard new customers.
* **Acceptance Criteria:**
  - Accessible only by users with the `super_admin` role.
  - Enters company name, domain, and uploads a company logo.
  - Submitting creates the Organization record in PostgreSQL and configures their isolated schema/scoping.
* **Scope / Phase:** Post-MVP (Deferred)

### US-1.5: Company Admin Creation UI
* **User Story:** As a Super Admin / Organization Admin, I want a user provisioning interface to invite and assign users as Company Admins or HR Managers within the organization.
* **Acceptance Criteria:**
  - `super_admin` can create admins for any company; `organization_admin` can only create users/HR within their own company scope.
  - Generates a registration invite link sent via email to the new user.
* **Scope / Phase:** Post-MVP (Deferred)

---

## Epic 2: Job Description (JD) Management & Parsing (JD Pipeline)

### US-2.1: Draft Job Creation (Title-Only)
* **User Story:** As an HR User, I want to create a new job posting by entering just a job title so that I have a draft record immediately available without filling out details.
* **Acceptance Criteria:**
  - Submitting only a job title to `POST /api/v1/jobs` returns `201 Created` with a new job UUID.
  - The job record is saved with status `draft`.
* **Scope / Phase:** MVP (Phase 2: JD Pipeline)

### US-2.2: Immediate AI Job Description Parsing
* **User Story:** As an HR User, I want to paste raw JD text or upload a PDF/DOCX document during job creation so that the AI parser automatically extracts structured requirements in real time.
* **Acceptance Criteria:**
  - Backend accepts raw text or a file stream, parses document text via `docling`, and invokes `gemma4:31b` to return structured JSON.
  - Extracted fields: required skills, preferred skills, minimum experience years, education requirements, job type, work mode, and location.
  - No values are hallucinated if not present (missing fields are stored as `null`).
  - The API returns extracted fields to the frontend form immediately for inline review.
  - If extraction fails (e.g., LLM timeout), the worker retries 3x. On final failure, status changes to `extraction_failed` and displays a manual retry button.
* **Scope / Phase:** MVP (Phase 2: JD Pipeline)

### US-2.3: Job Detail Editing & Review
* **User Story:** As an HR User, I want to view and edit the parsed draft job description criteria so that I can correct any inaccuracies before publishing the job.
* **Acceptance Criteria:**
  - HR can edit fields inline: title, required skills, preferred skills, experience range, location, and work mode.
  - Edits are saved using `PUT /api/v1/jobs/:id`.
* **Scope / Phase:** MVP (Phase 2: JD Pipeline)

### US-2.4: Job Publishing Gate Validation
* **User Story:** As an HR User, I want to publish the job description so that candidates can view and apply to it.
* **Acceptance Criteria:**
  - Attempting to transition status to `published` checks that the job has a non-empty `title` and at least one item in `required_skills`.
  - Publishing without these validation criteria returns a `422 Unprocessable Entity` error.
  - Published jobs are returned on the public endpoints.
* **Scope / Phase:** MVP (Phase 2: JD Pipeline)

### US-2.5: Job Closing & Archiving
* **User Story:** As an HR User, I want to close an active job posting so that candidates can no longer see or apply to it.
* **Acceptance Criteria:**
  - Transitioning status from `published` to `closed` is immediate.
  - Closed jobs are hidden from public API lists but remain visible in the HR dashboard.
* **Scope / Phase:** MVP (Phase 2: JD Pipeline)

---

## Epic 3: Candidate Public Board & Application Submission (Application Pipeline)

### US-3.1: Public Job Board Browsing
* **User Story:** As a Candidate, I want to browse active job openings for a specific company without creating an account so that there is no friction to finding open roles.
* **Acceptance Criteria:**
  - The public endpoint `GET /api/v1/public/jobs` returns only jobs with `status = published` scoped to the subdomain host (e.g., `acme.ezscreen.io`).
  - Candidates can view basic job metadata and descriptions without authentication.
* **Scope / Phase:** MVP (Phase 3: Application Pipeline)

### US-3.2: Guest Application Form Submission
* **User Story:** As a Candidate, I want to apply to a job by uploading my resume PDF/DOCX and entering my contact details (Name, Email, Phone) as a guest so that the application process is fast and frictionless.
* **Acceptance Criteria:**
  - Application submission accepts name, email, phone, and a resume document key.
  - The client uploads files directly to object storage via a pre-signed URL before submitting.
  - File upload validations enforce PDF or DOCX formats (checked by MIME and magic bytes) and a 10MB file size limit.
  - If valid, a new application record is created with `status = applied`.
* **Scope / Phase:** MVP (Phase 3: Application Pipeline)

### US-3.3: Duplicate Application Block
* **User Story:** As a Candidate, I want the system to prevent me from applying multiple times to the same job so that I don't submit duplicate profiles.
* **Acceptance Criteria:**
  - System enforces a composite unique constraint: `(job_description_id, candidate_email)`.
  - Resubmitting with an existing email for the same job ID returns `409 Conflict`.
* **Scope / Phase:** MVP (Phase 3: Application Pipeline)

### US-3.4: Application Confirmation Email
* **User Story:** As a Candidate, I want to receive an automated email confirmation of my application so that I know it was successfully received.
* **Acceptance Criteria:**
  - Email triggers asynchronously immediately after application creation.
  - Email contains job title, candidate name, and a GDPR opt-in link to register a candidate account in the future if they choose.
* **Scope / Phase:** MVP (Phase 5: Polish & Deploy)

---

## Epic 4: AI Resume Screening & Scoring (Core Matching Engine)

### US-4.1: Asynchronous Resume Parsing
* **User Story:** As the system, I want to automatically extract text from candidate resumes in the background so that we have structured profile details for matching.
* **Acceptance Criteria:**
  - Triggers immediately after application creation.
  - Downloads the resume from S3, parses using `docling`, and invokes `gemma4:31b` to populate the `parsed_resume` JSONB table (summary, primary skills, secondary skills, experience timeline, total years, education, certifications).
  - Overlapping job tenures are deduplicated (not just summed up) to calculate true `total_experience_years`.
* **Scope / Phase:** MVP (Phase 3: Application Pipeline)

### US-4.2: Resume-JD Weighted Match Scoring
* **User Story:** As the system, I want to compare candidate resume qualifications against the published JD requirements so that candidates can be ranked objectively.
* **Acceptance Criteria:**
  - Compares `parsed_resume` JSONB against the JD `parsed_jd` JSONB.
  - Calculates a 0.0 to 10.0 overall matching score using: `(skills * 0.40 + experience * 0.35 + education * 0.25) * 10`.
  - Generates a fit recommendation (`strong_fit`, `moderate_fit`, `weak_fit`, `not_suitable`), list of matched skills, missing skills, strengths, and concerns.
  - Writes the matching result to the `matching_result` JSONB and denormalizes `resume_score` and `candidate_yoe` for fast sorting.
  - Transitions application status to `resume_screened` (or error state on failure).
* **Scope / Phase:** MVP (Phase 3: Application Pipeline)

---

## Epic 5: HR Recruitment Dashboard & Action Management

### US-5.1: HR Ranked Applicant Dashboard
* **User Story:** As an HR User, I want to view a ranked list of candidates for a job description sorted by their AI matching score so that I can immediately focus on the strongest candidates.
* **Acceptance Criteria:**
  - Dashboard shows candidate name, match score (0-10), skills match bar, experience years, application date, and status badge.
  - Default sort order is `matching_score DESC`.
  - Supports filtering by status, score range, and experience range.
  - Supports sorting by application date, name, and experience years.
* **Scope / Phase:** MVP (Phase 4: HR Review & Scheduling)

### US-5.2: Visual Profile Match Breakdown
* **User Story:** As an HR User, I want to open a candidate's profile page and see their visual match details so that I can review their specific skills, experience gaps, and the AI evaluation summary.
* **Acceptance Criteria:**
  - Profile page shows candidate contact info, parsed experience timeline, education, and certifications.
  - Displays visual score breakdown (Skills/Experience/Education matches).
  - Highlights matched skills in green and missing required skills in red.
  - Displays AI-generated strengths, concerns, and overall summary text.
  - Includes a signed download link for the resume PDF (15-min TTL).
* **Scope / Phase:** MVP (Phase 4: HR Review & Scheduling)

### US-5.3: HR Status Actions
* **User Story:** As an HR User, I want to transition a candidate application status to `shortlist_for_l1` or `rejected` so that the pipeline moves forward and the status change is audit logged.
* **Acceptance Criteria:**
  - Status transition buttons are visible on candidate detail view.
  - Clicking `Reject` prompts HR to confirm and triggers a rejection email.
  - All status updates are written to the audit log.
* **Scope / Phase:** MVP (Phase 4: HR Review & Scheduling)

---

## Epic 6: Google Calendar & gMeet Scheduling

### US-6.1: Direct Interview Scheduling (Option A)
* **User Story:** As an HR User, I want to schedule a screening interview for a shortlisted candidate by inputting a date, time, and meeting details so that the candidate is invited and the session is logged.
* **Acceptance Criteria:**
  - Creates an `interview_session` record with `status = scheduled`.
  - API connects to Google Calendar API to create an event, generate a Google Meet URL, and send a confirmation email to the candidate with the meet link and calendar invite attachment (.ics).
* **Scope / Phase:** MVP (Phase 4: HR Review & Scheduling)

---

## Epic 7: AI Meeting Bot & Automated Call Screening (Attendee Bot)

### US-7.1: Compatibility Matching Question Auto-Generation
* **User Story:** As the system, I want to auto-generate tailored interview questions based on the compatibility match between the candidate's resume and the job description requirements so that the bot can screen the candidate on their alignment with the role.
* **Acceptance Criteria:**
  - Runs as a background task upon interview scheduling.
  - Generates 5-7 questions covering core role competencies, required experience context, and technical compatibility.
  - Saves questions inside `interview_session.generated_questions`.
* **Scope / Phase:** MVP (Phase 4: HR Review & Scheduling)

### US-7.2: Headless Meeting Bot Joining & Recording (Attendee.dev)
* **User Story:** As the system, I want to dispatch a virtual meeting bot (Attendee.dev) to join the scheduled Google Meet call so that the bot can conduct the interview, record audio, and capture the conversation transcript.
* **Acceptance Criteria:**
  - Dispatch triggers automatically at the interview start time via API call to `POST app.attendee.dev/api/v1/bots`.
  - Bot enters Google Meet room with display name "EZScreen Screening Assistant".
  - Bot captures dual-channel audio and streams audio/closed caption frames.
  - On call finish or `/leave` API trigger, bot leaves, and system transitions status to `interview_completed`.
* **Scope / Phase:** MVP (Phase 4: HR Review & Scheduling)

### US-7.3: LLM Conversation Pipeline
* **User Story:** As the system, I want the bot to speak the generated questions and respond to candidate answers in real time during the call so that the candidate experiences a natural interactive screening session.
* **Acceptance Criteria:**
  - WebSockets connection manages raw room audio.
  - Integrates STT to convert candidate speech, LLM (`gemma4:31b`) to generate follow-up/next questions, and TTS to synthesize bot speech played back on call.
* **Scope / Phase:** MVP (Phase 4: HR Review & Scheduling)

### US-7.4: Post-Interview Screening Evaluation Report
* **User Story:** As the system, I want to evaluate the completed interview transcript in the background so that I can write a detailed screening analysis report for HR.
* **Acceptance Criteria:**
  - Triggered on webhook completion of transcript.
  - Evaluates competency signals, communication skills, technical depth, and highlights transcript Q&A.
  - Saves the report to `interview_analysis` table.
  - Generates a recommendation: `proceed` / `reject` / `next_round`.
* **Scope / Phase:** MVP (Phase 4: HR Review & Scheduling)

### US-7.5: HR Screening Report Review
* **User Story:** As an HR User, I want to view the screening report, dual-channel transcript, and overall rating on the candidate's profile so that I can easily decide whether to move the candidate to L1 or reject.
* **Acceptance Criteria:**
  - HR opens report view. Displays question-by-question candidate response scoring, general remarks, and overall fit recommendation.
* **Scope / Phase:** MVP (Phase 4: HR Review & Scheduling)


