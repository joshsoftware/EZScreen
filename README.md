# EZScreen - AI-Powered Recruitment Platform

EZScreen is an AI-powered candidate screening and interview automation system. This repository is organized as a monorepo containing the following components:

## Monorepo Layout

* **`apps/frontend`**: React Single Page Application built with Vite, TypeScript, and TailwindCSS.
* **`apps/core-api`**: Core platform backend powered by FastAPI (Python), responsible for multi-tenancy, authentication, DB orchestration, and background worker task distribution.
* **`services/ai-core-services`**: Unified AI Microservice handling real-time WebSockets, STT-LLM-TTS chaining, Attendee bot synchronization, and background parsing, matching.
* **`docs/`**: Requirements, Architecture, MVP, and Integration guides.

---

## Local Development Setup

To spin up the database, cache, local object storage, and all application services, run:

```bash
docker compose up -d --build
```

### Services Access

* **React Frontend**: [http://localhost:5173](http://localhost:5173)
* **Core API Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
* **AI Core Services Swagger UI**: [http://localhost:8002/docs](http://localhost:8002/docs)
* **MinIO Storage Console**: [http://localhost:9001](http://localhost:9001) (Credentials: `minio_admin` / `minio_password`)
* **PostgreSQL Database**: `localhost:5433` (Credentials: `ezscreen_user` / `ezscreen_password`)

