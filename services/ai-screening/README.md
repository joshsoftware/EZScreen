# Primary Responsibilities of the AI Screening Service

The **AI Screening Service** is an internal microservice responsible for AI processing tasks across the recruitment pipeline:

## Core Responsibilities

- **Job Description (JD) Parsing**: Extracting structured requirement criteria (`parsed_jd` JSONB) from raw text or uploaded PDF/DOCX documents.
- **Resume Parsing**: Extracting candidate skills, experience, and education (`parsed_resume` JSONB) from uploaded resumes.
- **Resume & JD Matching**: Evaluating candidate fit against job criteria to calculate `resume_score` (0–100) and `matching_result` JSONB.
- **Question Generation**: Generating candidate-tailored static interview questions (`generated_questions` JSONB containing `id`, `question`, `expected_keywords`, `example_depth`, `follow_up`) based on matching results and skill gaps.
- **Bot-Based Screening Interviews**: Orchestrating Attendee.dev meeting bots to join Google Meet calls, record dual-channel audio, and run real-time STT $\rightarrow$ LLM $\rightarrow$ TTS conversation pipelines.
- **Candidate Interview Analysis**: Evaluating complete call transcripts post-interview using `gemma4:31b` to generate structured `interview_analysis` records (`analysis_result` JSONB + `question_answer` transcript scoring + recording URL).

## Key Technical Specifics

- **Internal Base URL**: `http://ai-screening:8002/internal/v1`
- **LLM Engine**: `gemma4:31b` (open-weight 31B parameter model providing structured JSON output)
- **Meeting Bot Integration**: Attendee.dev API for Google Meet audio capture and webhook ingestion
- **Inter-Service Communication**: REST over internal cluster network (`apps/core-api` $\leftrightarrow$ `services/ai-screening`)

## Microservice API Endpoints (Short Reference)

- `POST /internal/v1/parse/jd` — Parse raw JD text/file into structured `parsed_jd` JSON.
- `POST /internal/v1/parse/resume` — Parse candidate resume binary into `parsed_resume` JSON.
- `POST /internal/v1/match/resume-jd` — Score candidate resume against JD (`resume_score` & `matching_result`).
- `POST /internal/v1/screening/questions/generate` — Generate static interview questions (`generated_questions`).
- `POST /internal/v1/screening/bot/dispatch` — Dispatch Attendee.dev meeting bot to Google Meet URL.
- `POST /internal/v1/screening/analysis/evaluate` — Evaluate call transcript to generate `interview_analysis`.
