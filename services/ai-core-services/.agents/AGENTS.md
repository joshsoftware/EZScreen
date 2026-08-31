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
├── screening_pipeline/  # STT/TTS (planned)
└── interview_analysis/  # Post-call evaluation (planned)
```

## Layering rules

1. **API layer** (`api/v1/`) — request/response only; no LLM prompts or business formulas
2. **Domain layer** — orchestration (`matcher.py`, parsers); accepts injected clients
3. **Pure logic** — `score_calculator.py`, schema validation; no I/O, fully unit-testable
4. **Prompts** — `prompt_builder.py` per domain; large templates stay out of orchestrators

## Testing strategy

- `tests/job_fit_analysis/test_score_calculator.py` — deterministic scoring math
- `tests/parsing/test_schemas.py` — Pydantic model validation
- `tests/api/v1/` — route tests with mocked domain services
- Never hit real Ollama/MinIO/Attendee in unit tests
