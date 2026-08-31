# EZScreen - AI-Powered Recruitment Platform

EZScreen is an AI-powered candidate screening and interview automation system. This repository is organized as a monorepo containing the following components:

## Monorepo Layout

* **`apps/frontend`**: React Single Page Application built with Vite, TypeScript, and TailwindCSS.
* **`apps/core-api`**: Core platform backend powered by FastAPI (Python), responsible for multi-tenancy, authentication, DB orchestration, and background worker task distribution.
* **`services/ai-core-services`**: Unified AI Microservice handling real-time WebSockets, STT-LLM-TTS chaining, Attendee bot synchronization, and background parsing, matching.
* **`docs/`**: Requirements, Architecture, MVP, and Integration guides.

---

## Local Development Setup

To spin up the database, cache, local object storage, and all application services:

```bash
cp apps/core-api/.env.example apps/core-api/.env
cp services/ai-core-services/.env.example services/ai-core-services/.env
# Set POSTGRES_* + DATABASE_URL in core-api/.env
# Set MINIO_ROOT_* + MINIO_ACCESS_KEY/SECRET_KEY in ai-core-services/.env (same values)

docker compose up -d --build
```

### Services Access

* **React Frontend**: [http://localhost:5173](http://localhost:5173)
* **Core API Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
* **AI Core Services Swagger UI**: [http://localhost:8002/docs](http://localhost:8002/docs)
* **MinIO Storage Console**: [http://localhost:9003](http://localhost:9003) (see `MINIO_ROOT_*` in `services/ai-core-services/.env`)
* **PostgreSQL Database**: `localhost:5434` (see `POSTGRES_*` in `apps/core-api/.env`)

