# EZScreen — From-Scratch Setup Guide

Complete local setup for a **new machine** that only has **Git** installed and authenticated. Follow this document top to bottom.

---

## What you are setting up

| Component | Path | Role | Default URL |
|-----------|------|------|-------------|
| Frontend | `apps/frontend` | React + Vite UI | http://localhost:5173 |
| Core API | `apps/core-api` | FastAPI auth, jobs, ATS | http://localhost:8000 |
| AI Core | `services/ai-core-services` | Parsing, matching, screening AI | http://localhost:8002 |
| PostgreSQL | Docker `db` | Primary database | `localhost:5434` |
| MinIO | Docker `minio` | Resume / JD object storage | API `localhost:9002`, Console http://localhost:9003 |

**Recommended path:** install Docker → fill `.env` files → start Compose → **database from scratch** (Postgres role/DB via Compose, Alembic migrations, super admin) → verify.

**Optional path:** run Postgres + MinIO in Docker, run Python/Node apps natively on the host (for faster iteration).

---

## 1. Prerequisites (install once)

### 1.1 Operating system

These steps assume **Ubuntu / Debian-like Linux**. Adjust package names for macOS (Homebrew) or Windows (WSL2 strongly recommended).

### 1.2 Git (already done)

Confirm:

```bash
git --version
git config --global user.name
# SSH to GitHub should work:
ssh -T git@github.com
```

If SSH fails, add an SSH key to GitHub or use HTTPS with a personal access token.

### 1.3 Docker Engine + Compose plugin

```bash
# Official convenience script (Linux)
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER"
# Log out and back in (or reboot) so the docker group applies
docker version
docker compose version
```

You need Docker **and** the Compose V2 plugin (`docker compose`, not only legacy `docker-compose`).

### 1.4 Tools used outside Docker (scripts / optional native run)

```bash
sudo apt update
sudo apt install -y \
  curl \
  openssl \
  build-essential \
  libpq-dev \
  postgresql-client \
  python3 \
  python3-venv \
  python3-pip
```

`postgresql-client` provides `psql` for verifying the DB from the host (optional but useful).

Install **Node.js 18+** (frontend Dockerfile uses Node 18):

```bash
# Example: NodeSource 20.x
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
node -v   # v18+ or v20+
npm -v
```

Optional but useful for AI-core native work: [uv](https://github.com/astral-sh/uv)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 1.5 Disk / RAM notes

- First `docker compose up --build` downloads base images and builds AI deps (Docling / CPU PyTorch). Expect **several GB** and a long first build.
- AI PDF OCR is off by default (`DOCLING_DO_OCR=false`) to keep memory reasonable on smaller machines.

---

## 2. Clone the repository

```bash
git clone git@github.com:joshsoftware/EZScreen.git
cd EZScreen
```

If you use HTTPS:

```bash
git clone https://github.com/joshsoftware/EZScreen.git
cd EZScreen
```

Checkout the branch your team uses for local work (ask if unsure):

```bash
git fetch origin
git checkout <branch-name>
```

---

## 3. Create environment files

**Never commit `.env` files.** Copy the examples, then edit.

```bash
cp apps/core-api/.env.example apps/core-api/.env
cp services/ai-core-services/.env.example services/ai-core-services/.env
cp apps/frontend/.env.example apps/frontend/.env
```

### 3.1 Generate shared secrets

Run these and paste the values into the `.env` files:

```bash
# JWT signing secret
openssl rand -hex 32

# Internal service token (core-api ↔ ai-core-services)
openssl rand -hex 32

# Strong DB / MinIO passwords (pick your own; avoid spaces)
openssl rand -base64 24
```

### 3.2 Values that **must match** across files

| Concept | `apps/core-api/.env` | `services/ai-core-services/.env` |
|---------|----------------------|----------------------------------|
| DB user | `POSTGRES_USER` | (same user in `DATABASE_URL`) |
| DB password | `POSTGRES_PASSWORD` | password in `DATABASE_URL` (**URL-encoded**) |
| DB name | `POSTGRES_DB` | same in `DATABASE_URL` |
| Internal token | `INTERNAL_SERVICE_TOKEN` | `INTERNAL_SERVICE_TOKEN` (**identical**) |
| MinIO access | `MINIO_ACCESS_KEY` | `MINIO_ROOT_USER` **and** `MINIO_ACCESS_KEY` |
| MinIO secret | `MINIO_SECRET_KEY` | `MINIO_ROOT_PASSWORD` **and** `MINIO_SECRET_KEY` |

**URL-encode special characters** in passwords inside `DATABASE_URL` (e.g. `!` → `%21`, `@` → `%40`, `#` → `%23`).

Example: password `EZScreen123!` → `EZScreen123%21` in the URL.

### 3.3 Recommended local Docker Compose values

#### `apps/core-api/.env` (Compose)

```env
POSTGRES_USER=ezscreen_user
POSTGRES_PASSWORD=CHANGE_ME_STRONG_PASSWORD
POSTGRES_DB=ezscreen_db
POSTGRES_HOST_PORT=5434
# Password in URL must be URL-encoded; host "db" is the Compose service name
DATABASE_URL=postgresql+psycopg2://ezscreen_user:CHANGE_ME_URL_ENCODED@db:5432/ezscreen_db

JWT_SECRET=CHANGE_ME_LONG_RANDOM
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=7
REFRESH_COOKIE_SECURE=false
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
FRONTEND_BASE_URL=http://localhost:5173

# Browser opens this host — use published host port, NOT Docker DNS "minio"
MINIO_ENDPOINT=127.0.0.1:9002
MINIO_ACCESS_KEY=minio_admin
MINIO_SECRET_KEY=CHANGE_ME_MINIO_SECRET
MINIO_SECURE=false
MINIO_BUCKET_RESUMES=resumes

# Compose overrides AI_SERVICES_HOST to ai-core-services; 127.0.0.1 is fine as fallback
AI_SERVICES_HOST=127.0.0.1
AI_SERVICES_PORT=8002

INTERNAL_SERVICE_TOKEN=CHANGE_ME_IDENTICAL_IN_BOTH_ENVS

EMAIL_MODE=console
EMAIL_FROM=noreply@ezscreen.io

# Local default: placeholder Meet links (no Google credentials required)
GOOGLE_MEET_MODE=mock
GOOGLE_CALENDAR_ID=primary
GOOGLE_CALENDAR_SEND_UPDATES=all
```

#### `services/ai-core-services/.env` (Compose)

```env
SERVICE_NAME=ai-core-services
PORT=8002
LOG_LEVEL=INFO
ENVIRONMENT=development

# LLM — required for parsing / matching / questions (see §7)
OLLAMA_URL=https://ollama.com
OLLAMA_MODEL=gemma4:31b
OLLAMA_API_KEY=your_ollama_cloud_api_key

# Compose sets CORE_API_* via docker-compose.yml; keep a localhost fallback for native runs
CORE_API_URL=http://localhost:8000
CORE_API_BASE_URL=http://127.0.0.1:8000
INTERNAL_SERVICE_TOKEN=CHANGE_ME_IDENTICAL_IN_BOTH_ENVS

DATABASE_URL=postgresql://ezscreen_user:CHANGE_ME_URL_ENCODED@db:5432/ezscreen_db

MINIO_ENDPOINT=minio:9000
MINIO_ROOT_USER=minio_admin
MINIO_ROOT_PASSWORD=CHANGE_ME_MINIO_SECRET
MINIO_ACCESS_KEY=minio_admin
MINIO_SECRET_KEY=CHANGE_ME_MINIO_SECRET
MINIO_SECURE=false
MINIO_BUCKET_NAME=resumes
MINIO_API_HOST_PORT=9002
MINIO_CONSOLE_HOST_PORT=9003

DOCLING_DO_OCR=false

# Live screening / bots — optional until you need them (see §7)
ATTENDEE_API_KEY=
ATTENDEE_API_URL=https://api.attendee.dev/v1
WEBHOOK_URL=https://your-ngrok-url/screening/webhook
WHISPER_API_URL=https://api.groq.com/openai/v1/audio/transcriptions
WHISPER_API_KEY=
KOKORO_API_URL=https://api.replicate.com/v1/predictions
KOKORO_API_KEY=
WEBSOCKET_URL=wss://dummy-ezscreen.ngrok.io/audio
```

#### `apps/frontend/.env`

```env
# Empty = browser calls /api on same origin (Vite proxy → core-api)
VITE_CORE_API_URL=

# Optional: Google Drive picker for resume upload
# VITE_GOOGLE_CLIENT_ID=
# VITE_GOOGLE_API_KEY=
```

Compose sets `DEV_API_PROXY_TARGET=http://core-api:8000` for the frontend container automatically.

### 3.4 Compose and host-port variables

`POSTGRES_HOST_PORT`, `MINIO_API_HOST_PORT`, and `MINIO_CONSOLE_HOST_PORT` are substituted by Compose. Either:

- pass both env files when starting Compose (recommended), or  
- put those three keys in a project-root `.env` (Compose auto-loads it).

---

## 4. Start everything with Docker Compose (recommended)

From the **repo root**:

```bash
docker compose \
  --env-file apps/core-api/.env \
  --env-file services/ai-core-services/.env \
  up -d --build
```

First build can take a long time. Watch progress:

```bash
docker compose ps
docker compose logs -f --tail=100
```

Healthy baseline:

| Container | Expected |
|-----------|----------|
| `ezscreen-db` | healthy |
| `ezscreen-minio` | healthy |
| `ezscreen-minio-init` | exited 0 (creates `resumes` + `jds` buckets) |
| `ezscreen-core-api` | running on `:8000` |
| `ezscreen-ai-core-services` | running on `:8002` |
| `ezscreen-frontend` | running on `:5173` |

---

## 5. Database setup from scratch

PostgreSQL is empty on first boot. The Compose `db` service only creates the **role + database**; it does **not** create application tables. Tables come from **Alembic migrations** in `apps/core-api`. There is no automatic migrate-on-startup.

Schema design reference: [architecture/DB_DESIGN.md](./architecture/DB_DESIGN.md).

### 5.1 What Compose creates for you

`docker-compose.yml` runs `postgres:15-alpine` as service `db` (`ezscreen-db`).

On **first** container start (empty `pgdata` volume), Postgres reads these from `apps/core-api/.env`:

| Env var | Effect |
|---------|--------|
| `POSTGRES_USER` | Creates this DB role (e.g. `ezscreen_user`) |
| `POSTGRES_PASSWORD` | Password for that role |
| `POSTGRES_DB` | Creates this database (e.g. `ezscreen_db`) owned by that role |

Host publish: `POSTGRES_HOST_PORT` (default **5434**) → container `5432`.

Data is stored in Docker volume **`pgdata`**. Changing `POSTGRES_*` later does **not** recreate the user/DB unless you remove the volume (`docker compose down -v`).

Both services must share the same credentials:

| File | Connection string |
|------|-------------------|
| `apps/core-api/.env` | `DATABASE_URL=postgresql+psycopg2://USER:ENCODED_PASS@db:5432/DB` (Compose) |
| `services/ai-core-services/.env` | `DATABASE_URL=postgresql://USER:ENCODED_PASS@db:5432/DB` (Compose) |

Same `USER` / password / `DB`. Password in the URL must be **URL-encoded** if it contains `! @ # %` etc.

### 5.2 Start Postgres only (optional first step)

Useful before building the heavy AI image:

```bash
# From repo root, after .env files exist
docker compose \
  --env-file apps/core-api/.env \
  --env-file services/ai-core-services/.env \
  up -d db
```

Wait until healthy:

```bash
docker compose ps db
# or
docker inspect --format='{{.State.Health.Status}}' ezscreen-db
# expect: healthy
```

### 5.3 Verify the empty database

**From the host** (install client if needed: `sudo apt install -y postgresql-client`):

```bash
# Replace user/db/password with your POSTGRES_* values
export PGPASSWORD='YourPostgresPassword'
psql -h 127.0.0.1 -p 5434 -U ezscreen_user -d ezscreen_db -c '\conninfo'
psql -h 127.0.0.1 -p 5434 -U ezscreen_user -d ezscreen_db -c '\dt'
# On a fresh DB, \dt shows "Did not find any relations." until migrations run
```

**From inside the container:**

```bash
docker compose exec db \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c 'SELECT version();'
```

Or hardcode:

```bash
docker compose exec db psql -U ezscreen_user -d ezscreen_db -c 'SELECT current_database(), current_user;'
```

### 5.4 How migrations work

| Item | Location / command |
|------|--------------------|
| Alembic config | `apps/core-api/alembic.ini` |
| Env (reads `DATABASE_URL` from settings / `.env`) | `apps/core-api/alembic/env.py` |
| Migration scripts | `apps/core-api/alembic/versions/` |
| Apply all | `alembic upgrade head` |
| Current revision | `alembic current` |
| History | `alembic history` |

Core API does **not** call `create_all` on boot. Always run Alembic after a new DB or after pulling new migrations.

**Migration chain** (apply in order via `upgrade head`):

1. `c478691b4383` — initial schema (orgs, users, jobs, applications, interview tables, enums)
2. `d2a8f4c91b07` — job skills JSONB
3. `e3b9c5d82a14` — org settings JSONB
4. `f4c1a7e93b20` — password reset tokens
5. `a1c4e8b27d90` — application timeline
6. `b7e2d9f41c08` — backfill under_hr_review
7. `c9f3a1e82d04` — job screening questions

Initial tables include (among others): `organizations`, `users`, `job_descriptions`, `applications`, `interview_session`, `interview_analysis`, plus Alembic’s `alembic_version`.

### 5.5 Apply migrations (Docker — recommended)

With `core-api` running (or start it after `db` is healthy):

```bash
docker compose \
  --env-file apps/core-api/.env \
  --env-file services/ai-core-services/.env \
  up -d --build core-api

docker compose exec core-api alembic upgrade head
docker compose exec core-api alembic current
```

Expected: current revision at head (e.g. `c9f3a1e82d04` — confirm with `alembic history`).

### 5.6 Apply migrations (native host)

When apps run on the host and Postgres is published on `127.0.0.1:5434`:

```bash
cd apps/core-api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# DATABASE_URL in .env must use 127.0.0.1:5434 (not host "db")
alembic upgrade head
alembic current
```

### 5.7 Confirm schema

```bash
export PGPASSWORD='YourPostgresPassword'
psql -h 127.0.0.1 -p 5434 -U ezscreen_user -d ezscreen_db -c '\dt'
psql -h 127.0.0.1 -p 5434 -U ezscreen_user -d ezscreen_db \
  -c "SELECT version_num FROM alembic_version;"
```

You should see application tables and one row in `alembic_version`.

### 5.8 Create the first super admin

There is no default admin user. Create one after migrations:

```bash
# Docker
docker compose exec core-api python -m scripts.create_super_admin \
  --email admin@ezscreen.io \
  --password 'YourSecurePassword!'

# Native (venv active, cwd apps/core-api)
python -m scripts.create_super_admin \
  --email admin@ezscreen.io \
  --password 'YourSecurePassword!'
```

Options: `--first-name`, `--last-name`, `--update-password` (reset if user already exists).

Env overrides: `SUPER_ADMIN_EMAIL`, `SUPER_ADMIN_PASSWORD`, `SUPER_ADMIN_FIRST_NAME`, `SUPER_ADMIN_LAST_NAME`.

Verify:

```bash
psql -h 127.0.0.1 -p 5434 -U ezscreen_user -d ezscreen_db -c \
  "SELECT email, role, status FROM users WHERE role = 'super_admin';"
```

Login: **http://localhost:5173/super-admin/login**  
Org admin / HR (after you create orgs/users): **http://localhost:5173/org-admin/login**

### 5.9 Bootstrap product data (manual)

Migrations + super admin only. Next steps in the UI (or API):

1. Sign in as super admin  
2. Create an **organization**  
3. Invite / create **organization_admin** or **HR** users  
4. As org admin/HR: create jobs, upload resumes, schedule screenings  

Invite emails with `EMAIL_MODE=console` appear in **core-api logs**, not a real inbox.

### 5.10 Reset / wipe the database (dev only)

**A — Schema wipe + remigrate + optional admin** (keeps Docker volume; drops `public` schema):

```bash
docker compose exec core-api python -m scripts.reset_db --yes \
  --with-super-admin \
  --email admin@ezscreen.io \
  --password 'YourSecurePassword!'
```

`reset_db` uses container `DATABASE_URL` (`@db:5432` — correct inside Compose).

**B — Destroy Postgres data volume entirely** (fresh `POSTGRES_*` init on next start):

```bash
docker compose down
docker volume rm ezscreen_pgdata
# If the volume name differs:
docker volume ls | grep pgdata

docker compose \
  --env-file apps/core-api/.env \
  --env-file services/ai-core-services/.env \
  up -d db

# Wait healthy, then migrate + create admin again (§5.5–5.8)
```

Or wipe all Compose volumes (DB + MinIO + model caches):

```bash
docker compose down -v
```

**C — Full DROP DATABASE** (needs a Postgres superuser URL; uncommon with the stock Compose image, which has no separate `postgres` superuser password beyond `POSTGRES_USER`):

```bash
# Only if you have an admin URL; see apps/core-api/scripts/reset_db.py --help
python -m scripts.reset_db --yes --drop-database \
  --admin-url 'postgresql+psycopg2://ezscreen_user:PASS@127.0.0.1:5434/postgres'
```

Prefer **A** or **B** for local Docker.

### 5.11 Optional: Postgres without Docker

If you install Postgres on the host instead of Compose `db`:

```bash
sudo apt install -y postgresql postgresql-contrib
sudo service postgresql start

sudo -u postgres psql <<'SQL'
CREATE USER ezscreen_user WITH PASSWORD 'YourPostgresPassword';
CREATE DATABASE ezscreen_db OWNER ezscreen_user;
GRANT ALL PRIVILEGES ON DATABASE ezscreen_db TO ezscreen_user;
SQL
```

Then set both `DATABASE_URL`s to `127.0.0.1:5432` (or your port), skip starting Compose `db`, and run Alembic + `create_super_admin` as in §5.6–5.8. Keep `POSTGRES_*` in `.env` only if you still use the Compose `db` service.

### 5.12 Database troubleshooting

| Symptom | Cause | Fix |
|---------|--------|-----|
| `password authentication failed` | URL password ≠ `POSTGRES_PASSWORD`, or not URL-encoded | Fix both `DATABASE_URL`s; encode `!` as `%21`, etc. |
| Connection refused on `5434` | DB not up / wrong port | `docker compose ps db`; check `POSTGRES_HOST_PORT` |
| Connection to host `db` from laptop fails | `db` is Docker DNS only | From host use `127.0.0.1:5434` |
| `\dt` empty after “setup” | Migrations never run | `alembic upgrade head` |
| `relation already exists` | Partial schema / mixed reset | `reset_db --yes` or `down -v` then migrate clean |
| Changed `POSTGRES_PASSWORD` but login fails | Old credentials baked into `pgdata` | `docker compose down -v` (data loss) or alter role inside Postgres |
| AI service DB errors | ai-core `DATABASE_URL` wrong | Match user/pass/db to core-api; use `@db:5432` in Compose |
| Enum / column missing after pull | New migration not applied | `alembic upgrade head` again |

---

## 6. Verify the stack

Open or curl:

| Check | URL / command |
|-------|----------------|
| Frontend | http://localhost:5173 |
| Core API docs | http://localhost:8000/docs |
| AI Core docs | http://localhost:8002/docs |
| Core API root | `curl -s http://127.0.0.1:8000/` |
| MinIO console | http://localhost:9003 (login = `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD`) |
| Postgres | `psql` or any client → `127.0.0.1:5434`, user/db from `POSTGRES_*` |

Invite emails in local mode are printed to **core-api logs** (`EMAIL_MODE=console`):

```bash
docker compose logs -f core-api
```

---

## 7. Optional integrations (enable when needed)

Minimum viable local product loop (create org → job → upload resumes → parse/match) needs a working **LLM key** (`OLLAMA_*`). Other keys are feature-specific.

### 7.1 Ollama Cloud (LLM) — strongly recommended early

1. Create an API key at [ollama.com](https://ollama.com).
2. Set in `services/ai-core-services/.env`:
   - `OLLAMA_URL=https://ollama.com` (not `api.ollama.com`)
   - `OLLAMA_MODEL` (e.g. `gemma4:31b` or the model your team uses)
   - `OLLAMA_API_KEY=...`
3. Restart: `docker compose up -d --force-recreate ai-core-services`

### 7.2 Google Calendar + Meet (real screening links)

Default is `GOOGLE_MEET_MODE=mock` (placeholder Meet URLs). For live calendar events:

→ Follow **[docs/integrations/GOOGLE_CALENDAR_SETUP.md](./integrations/GOOGLE_CALENDAR_SETUP.md)**  
→ Set `GOOGLE_MEET_MODE=live` and OAuth (or service account) fields in `apps/core-api/.env`  
→ Recreate core-api

### 7.3 Google Drive picker (frontend resume import)

1. Google Cloud project: enable **Google Picker API** + **Drive API**.
2. Create a **Web** OAuth client; authorized JS origin: `http://localhost:5173`.
3. Set in `apps/frontend/.env`:
   - `VITE_GOOGLE_CLIENT_ID=...`
   - `VITE_GOOGLE_API_KEY=...`
4. Rebuild/restart frontend.

### 7.4 Attendee.dev meeting bot + public webhooks

Needed for live Meet bot / dual-channel audio:

1. Attendee API key → `ATTENDEE_API_KEY`
2. Public HTTPS tunnel (ngrok, Cloudflare Tunnel, etc.) pointing at AI core webhook  
   - `WEBHOOK_URL=https://<your-tunnel>/screening/webhook`
3. See **[docs/integrations/ATTENDEE_INTEGRATION.md](./integrations/ATTENDEE_INTEGRATION.md)**

### 7.5 STT / TTS (Groq Whisper, Replicate Kokoro)

Set `WHISPER_API_KEY` / `KOKORO_API_KEY` (and URLs if different) in `services/ai-core-services/.env` when exercising live audio pipelines.

---

## 8. Native development (optional)

Use when you want hot reload without rebuilding images. Keep **Postgres + MinIO** in Compose; run apps on the host.

### 8.1 Infra only

```bash
docker compose \
  --env-file apps/core-api/.env \
  --env-file services/ai-core-services/.env \
  up -d db minio minio-init
```

### 8.2 Adjust env for host processes

In **`apps/core-api/.env`** for native uvicorn:

```env
DATABASE_URL=postgresql+psycopg2://ezscreen_user:ENCODED_PASS@127.0.0.1:5434/ezscreen_db
MINIO_ENDPOINT=127.0.0.1:9002
AI_SERVICES_HOST=127.0.0.1
# Do not rely on Docker-only overrides
```

In **`services/ai-core-services/.env`** for native uvicorn:

```env
DATABASE_URL=postgresql://ezscreen_user:ENCODED_PASS@127.0.0.1:5434/ezscreen_db
MINIO_ENDPOINT=127.0.0.1:9002
CORE_API_URL=http://127.0.0.1:8000
CORE_API_BASE_URL=http://127.0.0.1:8000
```

### 8.3 Core API

```bash
cd apps/core-api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
python -m scripts.create_super_admin --email admin@ezscreen.io --password 'YourSecurePassword!'
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### 8.4 AI Core

```bash
cd services/ai-core-services
# Prefer uv if installed:
uv sync
uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8002
# Or: pip install with CPU torch index (see Dockerfile), then uvicorn
```

### 8.5 Frontend

```bash
cd apps/frontend
cp .env.example .env   # if not already
npm install
npm run dev
# Vite proxies /api → http://127.0.0.1:8000 by default
```

---

## 9. Day-to-day commands

```bash
# Start (after images built)
docker compose \
  --env-file apps/core-api/.env \
  --env-file services/ai-core-services/.env \
  up -d

# Stop
docker compose down

# Stop and delete volumes (wipes DB + MinIO data)
docker compose down -v

# Rebuild one service after Dockerfile / deps change
docker compose up -d --build core-api

# Logs
docker compose logs -f core-api ai-core-services frontend

# Shell into API
docker compose exec core-api bash
```

---

## 10. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Compose ignores `POSTGRES_HOST_PORT` / MinIO ports | Vars not in Compose substitution env | Pass `--env-file` for both service envs, or put ports in root `.env` |
| Presigned upload/download fails in browser | `MINIO_ENDPOINT` is `minio:9000` | Use `127.0.0.1:9002` in **core-api** `.env` (browser-reachable) |
| `password authentication failed` | `DATABASE_URL` password ≠ `POSTGRES_PASSWORD` or not URL-encoded | Align and encode special chars |
| AI → core-api callbacks 401 | Mismatched `INTERNAL_SERVICE_TOKEN` | Same value in both `.env` files; recreate both services |
| Empty schema / missing tables | Migrations not run | `docker compose exec core-api alembic upgrade head` |
| Port already in use | Another process on 5173/8000/8002/5434/9002 | Change `*_HOST_PORT` or stop the conflicting process |
| MinIO buckets missing | `minio-init` failed | `docker compose logs minio-init`; re-run compose |
| LLM / parse errors | Missing or wrong `OLLAMA_API_KEY` | Set key; confirm `OLLAMA_URL=https://ollama.com` |
| Frontend `/api` 502 in Docker | core-api not healthy | Check `docker compose ps` and core-api logs |
| PEP 668 / system pip blocked | Installing Python pkgs globally | Use `python3 -m venv` as shown above |

---

## 11. Security checklist (local)

- [ ] `.env` files are gitignored and never committed  
- [ ] `JWT_SECRET` and `INTERNAL_SERVICE_TOKEN` are random, not example placeholders  
- [ ] MinIO and Postgres passwords are not defaults you reuse elsewhere  
- [ ] `GOOGLE_MEET_MODE=mock` until Calendar OAuth is intentionally configured  
- [ ] Real API keys (Ollama, Groq, Attendee, Google) stay out of chat logs and PRs  

---

## 12. Related docs

| Doc | Topic |
|-----|--------|
| [README.md](../README.md) | Short monorepo overview |
| [integrations/GOOGLE_CALENDAR_SETUP.md](./integrations/GOOGLE_CALENDAR_SETUP.md) | Live Meet + Calendar |
| [integrations/ATTENDEE_INTEGRATION.md](./integrations/ATTENDEE_INTEGRATION.md) | Meeting bot |
| [architecture/SYSTEM_DESIGN.md](./architecture/SYSTEM_DESIGN.md) | System design |
| [architecture/DB_DESIGN.md](./architecture/DB_DESIGN.md) | Database |
| `services/ai-core-services/README.md` | AI microservice API map |

---

## Quick-start checklist (copy/paste)

```bash
# 0) Docker + Node + Python toolchain installed; re-login after docker group

# 1) Clone
git clone git@github.com:joshsoftware/EZScreen.git && cd EZScreen

# 2) Env
cp apps/core-api/.env.example apps/core-api/.env
cp services/ai-core-services/.env.example services/ai-core-services/.env
cp apps/frontend/.env.example apps/frontend/.env
# Edit both service .env files: matching passwords, tokens, MINIO_ENDPOINT=127.0.0.1:9002 in core-api

# 3) Up (Postgres creates POSTGRES_USER / POSTGRES_DB on first boot via empty pgdata volume)
docker compose \
  --env-file apps/core-api/.env \
  --env-file services/ai-core-services/.env \
  up -d --build

# 4) Database from scratch — migrate schema, then seed platform admin
docker compose exec core-api alembic upgrade head
docker compose exec core-api alembic current
docker compose exec core-api python -m scripts.create_super_admin \
  --email admin@ezscreen.io \
  --password 'YourSecurePassword!'

# Optional: confirm tables from host
# PGPASSWORD='...' psql -h 127.0.0.1 -p 5434 -U ezscreen_user -d ezscreen_db -c '\dt'

# 5) Open
xdg-open http://localhost:5173/super-admin/login   # or visit in browser
```
