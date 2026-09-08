# EZScreen: Attendee + MinIO

This Attendee clone is wired to **EZScreen MinIO** instead of AWS S3.

EZScreen core-api / frontend / ai-core keep normal Docker DNS (`db`, `minio`, `core-api`).
**Attendee** adapts ports/URLs to talk to that stack.

## Env

See `.env.example`. Important vars:

| Var | Value |
|-----|--------|
| `AWS_ENDPOINT_URL` | `http://host.docker.internal:9002` (EZScreen MinIO host port) |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | Same as `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` |
| `AWS_RECORDING_STORAGE_BUCKET_NAME` | `attendee-recordings` |
| `AWS_S3_ADDRESSING_STYLE` | `path` |
| `ALLOWED_HOSTS` | include `host.docker.internal` (ai-core calls Attendee) |
| `SITE_DOMAIN` | `localhost:8003` |

Optional: if Attendee is on `ezscreen_default` and container DNS works, you can use `AWS_ENDPOINT_URL=http://minio:9000` instead.

A ready `.env` can be generated locally; never commit it (gitignored).

## Run

1. EZScreen MinIO up + bucket created (`minio-init` creates `attendee-recordings`).
2. `docker compose -f dev.docker-compose.yaml up -d --build`
3. Migrate + open http://localhost:8003

4. Point ai-core at Attendee (in `services/ai-core-services/.env`):
   - `ATTENDEE_API_URL=http://host.docker.internal:8003`
   - `ATTENDEE_API_KEY=<key from Attendee dashboard>`

Attendee stays on its **own** Docker network and reaches MinIO via `host.docker.internal:9002`.
Do not attach Attendee to `ezscreen_default` — sharing that network broke container-to-container traffic on this host.

Full steps: `docs/SETUP.md` §7.4 Option B in the EZScreen repo root.
