# Google Calendar + Meet setup (EZScreen screening)

EZScreen **`GOOGLE_MEET_MODE=live`** creates a **Google Calendar event** with an auto-generated **Google Meet** link, sends calendar invites to attendees, then (by default) sets the Meet space to **`OPEN`** via the **Google Meet API** so anonymous bots can join without knocking.

---

## Prerequisites

- Google Cloud project (you already created this)
- **Google Workspace** account for the organizer (recommended)
  - e.g. `scheduler@yourcompany.com` or `hr@yourcompany.com`
- Meet enabled on that Workspace domain

---

## Step 1 — Enable APIs

1. Open [Google Cloud Console](https://console.cloud.google.com/) → select your project
2. **APIs & Services → Library**
3. Enable:
   - **Google Calendar API**
   - **Google Meet API** (required for `GOOGLE_MEET_ACCESS_TYPE=OPEN`)

---

## Step 2 — OAuth consent screen

1. **APIs & Services → OAuth consent screen**
2. **User type**
   - **Internal** — if all users are in your Workspace org (simplest)
   - **External** — for testing; add test users under **Test users**
3. Fill app name + support email
4. **Scopes → Add or remove scopes → Manually add**:

   ```text
   https://www.googleapis.com/auth/calendar.events
   https://www.googleapis.com/auth/meetings.space.created
   https://www.googleapis.com/auth/meetings.space.settings
   ```

5. Save

---

## Step 3 — Create OAuth credentials (development)

1. **APIs & Services → Credentials → Create credentials → OAuth client ID**
2. Application type: **Desktop app**
3. Download JSON (e.g. `client_secret.json`)

### Get refresh token

On Ubuntu/Debian, do **not** `pip install` into system Python (PEP 668). Use a one-time venv:

```bash
cd apps/core-api
python3 -m venv .venv-oauth
source .venv-oauth/bin/activate
pip install google-auth-oauthlib google-auth
python scripts/google_oauth_refresh_token.py --client-secrets /home/josh/Downloads/
deactivate
```

If `python3 -m venv` fails, install: `sudo apt install python3-venv`

Sign in as the **organizer** Google account (the calendar owner).

If the script prints “No refresh token returned”, revoke prior access at [Google Account permissions](https://myaccount.google.com/permissions) and re-run (needed after adding Meet scopes to an older token).

Copy the printed values into `apps/core-api/.env`:

```env
GOOGLE_MEET_MODE=live
GOOGLE_CALENDAR_ID=primary
GOOGLE_CALENDAR_SEND_UPDATES=all
GOOGLE_MEET_ACCESS_TYPE=OPEN
GOOGLE_OAUTH_CLIENT_ID=....apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=....
GOOGLE_OAUTH_REFRESH_TOKEN=....
```

---

## Step 4 — Service account (production / Workspace)

Use when HR should not run OAuth manually.

1. **Credentials → Create credentials → Service account**
2. Create key → **JSON** → download securely
3. **Google Workspace Admin** ([admin.google.com](https://admin.google.com))
   - **Security → Access and data control → API controls → Domain-wide delegation**
   - Add service account **Client ID**
   - Scopes:

     ```text
     https://www.googleapis.com/auth/calendar.events
     https://www.googleapis.com/auth/meetings.space.created
     https://www.googleapis.com/auth/meetings.space.settings
     ```

4. In `apps/core-api/.env`:

```env
GOOGLE_MEET_MODE=live
GOOGLE_CALENDAR_ID=primary
GOOGLE_CALENDAR_SEND_UPDATES=all
GOOGLE_MEET_ACCESS_TYPE=OPEN
GOOGLE_SERVICE_ACCOUNT_FILE=/run/secrets/google-sa.json
GOOGLE_MEET_DELEGATED_USER=scheduler@yourdomain.com
```

5. Mount JSON in Docker (`docker-compose.yml`):

```yaml
core-api:
  volumes:
    - ./secrets/google-service-account.json:/run/secrets/google-sa.json:ro
```

---

## Step 5 — Configure EZScreen

| Variable | Description |
|----------|-------------|
| `GOOGLE_MEET_MODE` | `mock` (dev) or `live` (Calendar + Meet) |
| `GOOGLE_CALENDAR_ID` | `primary` or organizer email calendar |
| `GOOGLE_CALENDAR_SEND_UPDATES` | `all` sends Google invites to attendees |
| `GOOGLE_MEET_ACCESS_TYPE` | `OPEN` (default), `TRUSTED`, `RESTRICTED`, or empty to skip Meet API patch |
| OAuth trio **or** service account + delegated user | See above |

Restart core-api:

```bash
docker compose up -d --build core-api
```

### How OPEN works

1. Calendar creates the event + Meet conference (as before)
2. Meet API `GET spaces/{meetingCode}` resolves the resource name
3. Meet API `PATCH` sets `config.accessType=OPEN`

If the patch fails (missing scope, Meet API disabled, or Workspace policy), scheduling still succeeds — check core-api logs for `Meet API accessType=… failed`. Org Meet admin settings can pin access type and override API changes (up to ~24h to propagate).

---

## Step 6 — Test in EZScreen

1. Publish a job → open an applicant under HR review
2. **Schedule screening** with a future date/time
3. Verify:
   - Timeline shows real `meet.google.com/...` link
   - Organizer Google Calendar has the event
   - Candidate receives Google calendar invite (if `GOOGLE_CALENDAR_SEND_UPDATES=all`)
   - Meet join settings show open / no knock (or core-api log: `Set Meet space … accessType=OPEN`)
   - `interview_metadata` contains `calendar_event_id`, `calendar_html_link`, `provider: google_calendar`

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| `Calendar API error: 403` | Enable Calendar API; check OAuth scope |
| `No Google Meet link was returned` | Workspace Meet not enabled for organizer |
| `Meet API accessType=… failed: 403` | Enable Meet API; re-mint refresh token with `meetings.space.*` scopes; check Workspace Meet access policies |
| `Invalid time_zone` | Use IANA name e.g. `Asia/Kolkata` |
| Service account fails | Set `GOOGLE_MEET_DELEGATED_USER`; verify domain-wide delegation includes all three scopes |
| Attendees not invited | Set `GOOGLE_CALENDAR_SEND_UPDATES=all` |

---

## What EZScreen stores

On schedule, `interview_session.interview_metadata` includes:

```json
{
  "gmeet_link": "https://meet.google.com/...",
  "calendar_event_id": "...",
  "calendar_html_link": "https://www.google.com/calendar/event?...",
  "provider": "google_calendar",
  "attendees": ["candidate@example.com"]
}
```

Attendee bot dispatch uses `gmeet_link` unchanged.
