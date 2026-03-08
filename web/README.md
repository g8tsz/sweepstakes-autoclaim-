# Casino Claim — Web App

Browser-based UI for the same automation as the Discord bot. Everything is **pages and buttons**: forms POST to the server and redirect back (no API calls from the page). Uses SQLite for users, profiles, run history, and 2FA state.

## Run

From the **project root** (parent of `web/`):

```bash
python run_web.py
```

Or with uvicorn directly:

```bash
uvicorn web.app:app --host 0.0.0.0 --port 8000
```

Then open http://localhost:8000

- **Login / Sign up** — Forms submit to `/login` and `/signup`; server sets session cookie and redirects to dashboard.
- **Dashboard** — Status (loop on/off), **Start loop** / **Stop loop** buttons (POST to `/loop/start`, `/loop/stop`), **Run now** form (select casino, POST to `/run`), 2FA form when required (POST to `/2fa`), recent runs list.
- **Profile** — **Save Google login** form (POST `/profile/google`), **Save casino** form (POST `/profile/casinos`). Server redirects back with `?msg=...` or `?error=...`.
- **History** — Server-rendered list of recent runs.

## Env (optional)

| Variable | Description |
|----------|-------------|
| `WEB_DATABASE_PATH` | SQLite file path (default: `web_data.db` in cwd) |
| `WEB_SECRET` | Secret for signing session cookies (set in production) |
| `WEB_WORKER_ENABLED` | Set to `0` to disable the background loop (e.g. no Chrome) |
| `WEB_LOOP_INTERVAL_SEC` | Seconds between full casino runs per user (default: 7200 = 2h) |
| `CHROME_INSTANCE_DIR` / `CHROME_USER_DATA_DIR` | Same as Discord bot for persistent Chrome profile |

## Flow

- **Loop**: When enabled per user, the worker runs all universal casinos (from `casinos_universal.json`) for that user every `WEB_LOOP_INTERVAL_SEC`. Uses the user’s profile Google/casino credentials from the DB.
- **Run now**: Triggers one casino run in the background; results appear in dashboard/history.
- **2FA**: When Google auth needs 2FA, the worker creates a pending 2FA row; the dashboard shows “2FA required” and a form to submit the code. The worker waits (polling DB) until the code is submitted or timeout.

## API (JSON)

- `POST /api/signup` — body: `{ "email", "password" }`
- `POST /api/login` — body: `{ "email", "password" }`
- `POST /api/logout`
- `GET /api/profile` — current user profile (passwords masked)
- `POST /api/profile/google` — body: `{ "email", "password" }`
- `POST /api/profile/casinos` — body: `{ "casino_name", "credentials" }`
- `GET /api/profile/list_casinos` — list of casino names
- `POST /api/loop/start` | `POST /api/loop/stop`
- `GET /api/status` — loop_enabled, pending_2fa, recent_runs, universal_casino_count
- `POST /api/run/{casino_key}` — run one casino now
- `GET /api/2fa` — pending 2FA if any
- `POST /api/2fa` — body: `{ "code" }` — submit 2FA code
