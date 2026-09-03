# ai-core-services Agent Guide

Python microservice (FastAPI, port 8002). Internal AI capabilities for EZScreen.

## Skills (read before major changes)

| Skill | Path | Use when |
|-------|------|----------|
| Project structure | `.agents/skills/python-project-structure/SKILL.md` | New modules, `__all__`, directory layout |
| Design patterns | `.agents/skills/python-design-patterns/SKILL.md` | Refactoring, layering, DI, SRP |
| Testing | `.agents/skills/python-testing-patterns/SKILL.md` | pytest, fixtures, mocking |

## Architecture

```
src/
├── main.py              # FastAPI app, router registration
├── core/                # config, logger, storage
├── common/              # llm_utils and shared helpers
├── llm/                 # OllamaClient wrapper
├── api/v1/              # HTTP controllers (/internal/v1/*)
├── parsing/             # JD & resume parsing
├── job_fit_analysis/    # Resume-JD matching & scoring
├── question_generation/ # Interview question generation
├── meeting_bot/         # Attendee.dev integration
├── screening_pipeline/  # Live interview: STT/TTS, evaluator, orchestrator
└── interview_analysis/  # Post-call evaluation (planned)
```

## Layering rules

1. **API layer** (`api/v1/`) — request/response only; no LLM prompts or business formulas
2. **Domain layer** — orchestration (`matcher.py`, parsers, `InterviewOrchestrator`); accepts injected clients
3. **Pure logic** — `score_calculator.py`, `experience_calculator.py`, `speech_filter.py`; no I/O
4. **Prompts** — `prompt_builder.py` per domain; large templates stay out of orchestrators

## API error pattern

Domain failures return HTTP 200 with `{ "status": "error", "error_message": "..." }` (parsing, matching, question generation, meeting bot). Prefer this over `HTTPException` for business/domain errors. Delete-bot success remains `204`; delete failures use the structured error body.

## Testing strategy

- `tests/job_fit_analysis/` — deterministic scoring math
- `tests/parsing/` — schemas + experience calculator
- `tests/question_generation/` — match context, question parsing, generator with mocked LLM
- `tests/screening_pipeline/` — evaluator builders, summary calculator, persistence, webhook, orchestrator mocks
- `tests/api/v1/` — route tests with mocked domain services
- Never hit real Ollama/MinIO/Attendee in unit tests
