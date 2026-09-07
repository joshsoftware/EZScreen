# EZScreen - AI-Powered Recruitment Platform

EZScreen is an AI-powered candidate screening and interview automation system. This repository is organized as a monorepo containing the following components:

## Monorepo Layout

* **`apps/frontend`**: React Single Page Application built with Vite, TypeScript, and TailwindCSS.
* **`apps/core-api`**: Core platform backend powered by FastAPI (Python), responsible for multi-tenancy, authentication, DB orchestration, and background worker task distribution.
* **`services/ai-core-services`**: Unified AI Microservice handling real-time WebSockets, STT-LLM-TTS chaining, Attendee bot synchronization, and background parsing, matching.
* **`docs/`**: Requirements, Architecture, MVP, and Integration guides.

---

## Local Development Setup

**New machine (Git only)?** Follow the full guide: **[docs/SETUP.md](docs/SETUP.md)**  
(prerequisites, env secrets, Compose, migrations, super admin, native option, troubleshooting).

Quick start if Docker is already installed:

```bash
cp apps/core-api/.env.example apps/core-api/.env
cp services/ai-core-services/.env.example services/ai-core-services/.env
cp apps/frontend/.env.example apps/frontend/.env
# Set matching POSTGRES_*/DATABASE_URL, MINIO_*, INTERNAL_SERVICE_TOKEN
# core-api MINIO_ENDPOINT should be 127.0.0.1:9002 for local Compose

docker compose \
  --env-file apps/core-api/.env \
  --env-file services/ai-core-services/.env \
  up -d --build

# Database from scratch: Compose creates the role/DB; Alembic creates tables; then seed admin
docker compose exec core-api alembic upgrade head
docker compose exec core-api python -m scripts.create_super_admin \
  --email admin@ezscreen.io \
  --password 'YourSecurePassword!'
```

Database details (empty Postgres → migrations → admin → reset): **[docs/SETUP.md §5](docs/SETUP.md#5-database-setup-from-scratch)**.

### Services Access

* **React Frontend**: [http://localhost:5173](http://localhost:5173) (super admin: `/super-admin/login`)
* **Core API Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
* **AI Core Services Swagger UI**: [http://localhost:8002/docs](http://localhost:8002/docs)
* **MinIO Storage Console**: [http://localhost:9003](http://localhost:9003) (see `MINIO_ROOT_*` in `services/ai-core-services/.env`)
* **PostgreSQL Database**: `localhost:5434` (see `POSTGRES_*` in `apps/core-api/.env`)

