# EZScreen AI Core Microservice (`services/ai-core-services`)

> **Port**: `8002`  
> **Base Internal Route**: `http://ai-core-services:8002/internal/v1`  
> **Runtime**: Python 3.11+, FastAPI, Ollama (`gemma4:31b`), Attendee.dev SDK

---

## 1. Overview & Service Responsibilities

The **AI Core Services** microservice is a unified, modular Python service co-locating all internal AI capability modules for the EZScreen platform:

* **Direct In-Memory JD Parsing**: Parses raw text or uploaded PDF/DOCX files in-memory to extract structured job requirement criteria (`parsed_jd` JSONB).
* **Resume Document Parsing**: Parses candidate resume binaries to extract structured candidate profiles (`parsed_resume` JSONB).
* **Custom Candidate-JD Matching Engine**: Evaluates candidate resumes against JD criteria using an in-house weighted formula to calculate `resume_score` (0.0 to 100.0) and `matching_result` JSONB.
* **Pre-Call Question Generation**: Auto-generates candidate-tailored static interview questions (`generated_questions` JSONB containing `id`, `question`, `expected_keywords`, `example_depth`, `follow_up`) targeting candidate skill gaps.
* **Attendee Meeting Bot Dispatching**: Dispatches Attendee.dev meeting bots to Google Meet URLs and handles live dual-channel audio streams via WebSockets.
* **Real-Time Audio Pipelines**:
  * **Speech-To-Text (STT)**: Transcribes candidate audio into real-time transcript text tokens.
  * **Text-To-Speech (TTS)**: Synthesizes AI question text and follow-ups into spoken voice audio streams.
* **Post-Call Transcript Evaluation**: Evaluates call transcripts using `gemma4:31b` to generate `interview_analysis` records (`analysis_result` JSONB + `question_answer` transcript scoring + recording URLs).

---

## 2. Architectural Design & Subsystem Organization

The microservice follows a **modular domain structure** with **shared generic functions** and **abstracted API route controllers**:

```
services/ai-core-services/src/
├── main.py                     # Central FastAPI application entrypoint
├── core/                       # Configuration, settings loader, & environment variables
│   ├── config.py
│   ├── logger.py
│   └── storage.py              # MinIO object storage client
│
├── common/                     # Shared generic utilities
│   └── llm_utils.py            # LLM JSON parsing helpers
│
├── llm/                        # Ollama / Gemma4 LLM client wrapper
│   └── client.py
│
├── api/                        # API controllers (/internal/v1/*)
│   └── v1/
│       ├── parsing.py
│       ├── matching.py
│       ├── question_generation.py
│       └── meeting_bot.py
│
└── DOMAIN MODULES:
    ├── parsing/                # JD & resume parsing
    ├── job_fit_analysis/       # Resume-JD matching & scoring
    ├── question_generation/    # Pre-call interview question generator
    ├── screening_pipeline/     # Real-time STT & TTS pipelines
    ├── meeting_bot/            # Attendee.dev bot dispatcher & WebSockets
    └── interview_analysis/     # Post-call transcript evaluator
```

---

## Agent Skills & Cursor Rules

Python conventions for AI-assisted development live in:

- **Skills**: `.agents/skills/` (design patterns, project structure, testing)
- **Compiled guide**: `.agents/AGENTS.md`

Run tests: `cd services/ai-core-services && uv run pytest`

---

## 3. Microservice Internal API Map

All endpoints are private inter-service APIs (`/internal/v1/*`) invoked internally by `apps/core-api`.

| Subsystem Module | Endpoint | Method | Responsibility |
| :--- | :--- | :--- | :--- |
| **Parsing** | `/internal/v1/parse/jd` | `POST` | Parses raw JD text/file in-memory $\rightarrow$ `parsed_jd` JSON. |
| **Parsing** | `/internal/v1/parse/resume` | `POST` | Parses candidate resume binary $\rightarrow$ `parsed_resume` JSON. |
| **Matching** | `/internal/v1/match/resume-jd` | `POST` | Calculates `resume_score` (0-100) & `matching_result` JSONB. |
| **Question Gen** | `/internal/v1/screening/questions/generate` | `POST` | Auto-generates static `generated_questions` array. |
| **Meeting Bot** | `/internal/v1/screening/bot/dispatch` | `POST` | Dispatches Attendee meeting bot to Google Meet URL. |
| **Interview Analysis** | `/internal/v1/screening/analysis/evaluate` | `POST` | Evaluates call transcript via `gemma4:31b` $\rightarrow$ `interview_analysis`. |

---

## 4. Key Technical Specifics & Configuration

* **Internal Port**: `8002`
* **Internal Base URL**: `http://ai-core-services:8002/internal/v1`
* **LLM Model**: `gemma4:31b` (open-weight model via Ollama / API Gateway)
* **Meeting Bot Provider**: Attendee.dev API (Google Meet audio capture & WebSockets)
* **Environment Template**: `.env.example`
