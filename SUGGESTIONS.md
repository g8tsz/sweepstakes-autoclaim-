# Suggestions for Casino Claim

Prioritized ideas to harden, improve, and extend the app. Use as a roadmap or pick items by priority.

---

## Security

### High

- **CSRF protection on forms**  
  All POST forms (login, signup, profile, loop, run, 2FA) are state-changing and currently have no CSRF token. Add a signed token in a hidden field (or double-submit cookie), validate on POST, and reject missing/invalid. Reduces risk of cross-site request forgery when the site is on a public URL.

- **Rate limit auth endpoints**  
  Limit failed login/signup attempts per IP (e.g. 10/minute) and optionally temporary lockout or captcha. Prevents brute force and credential stuffing. Implement in `web/app.py` (e.g. in-memory or Redis) or via a middleware.

- **Stricter session secret**  
  If `WEB_SECRET` is still `change-me-in-production`, refuse to start or show a startup warning. Prevents accidental production deploy with a known secret.

### Medium

- **Encrypt web profile credentials at rest**  
  `web/database.py` stores Google and casino credentials in SQLite in plaintext. Add optional encryption (e.g. Fernet key in env) for `google_login_encrypted` and `casino_credentials_json`, similar to Discord `profiles.py` with `PROFILE_ENCRYPTION_KEY`.

- **Secure headers**  
  Add middleware to set `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY` (or SAMEORIGIN), and when on HTTPS `Strict-Transport-Security`.

- **Password policy**  
  Enforce minimum length (e.g. 8) and optionally complexity on signup; show requirements on the signup page.

- **Content-Security-Policy (CSP)**  
  Add a restrictive CSP header to limit script/style sources and reduce XSS impact. Start with report-only mode, then enforce once stable.

- **Session binding**  
  Optionally bind session to IP or User-Agent so a stolen cookie is less useful from another device; document tradeoff (e.g. mobile IP changes).

### Low

- **Session invalidation**  
  Allow “log out everywhere” by storing a session version or nonce per user and invalidating on password change or explicit revoke.

- **Audit log for web**  
  Log signup, login (success/fail), profile changes, loop toggles (no credentials), e.g. to a file or table, for support and security review.

- **Sensitive fields in logs**  
  Ensure no passwords or tokens are ever logged; sanitize exception messages before writing to log files.

---

## Reliability & robustness

### High

- **Health/readiness endpoint**  
  Add `GET /health` or `GET /api/health` that returns 200 and optionally checks DB connectivity and worker liveness. Enables load balancers and monitoring without hitting real pages.

- **Graceful worker shutdown**  
  On app shutdown, cancel the worker task and give in-flight runs a short timeout (e.g. 30s) before exiting, so a run is not cut mid-flow. Already using `lifespan` and `stop_worker()`; ensure `run_one_casino_for_user` can be interrupted cleanly.

- **DB connection handling**  
  Use a single connection per request or a small pool; avoid opening a new SQLite connection on every `get_cursor()` under high load. Consider connection timeout and retry on lock.

### Medium

- **Retry/backoff for automation**  
  If a casino run fails (network, selector, etc.), optionally retry once or twice with a short delay before writing “error” to history. Reduces one-off flakiness.

- **Validate `casinos_universal.json`**  
  On load, validate required fields (`name`, `base_url`, etc.) and log clear errors for invalid entries so misconfig is easy to fix.

- **2FA timeout cleanup**  
  Periodically delete old `pending_2fa` rows (e.g. older than 1 hour) so the table does not grow and “no 2FA pending” stays accurate.

### Low

- **SQLite WAL mode**  
  Enable WAL for `web_data.db` for better concurrent read behavior during runs and page loads.
- **Structured error codes**  
  Return stable error codes or types (e.g. `invalid_credentials`, `rate_limited`) for login/signup so the UI or API clients can handle them consistently.

---

## Features

### High

- **Email verification (optional)**  
  On signup, send a verification link (e.g. with a signed token); require verified email before enabling loop or saving sensitive profile data. Needs a mailer (SMTP or SendGrid) and a simple “verify” route.

- **“Run now” queue feedback**  
  When the user clicks “Run now”, show that the run is queued or in progress (e.g. “Running WowVegas…”) and refresh when it finishes, instead of only showing result in history. Could use polling on `/api/status` or a simple “last_run” state.

- **Per-casino enable/disable**  
  Let users turn specific casinos on or off for the loop (e.g. checkboxes in profile or dashboard) instead of all-or-nothing. Store in DB and filter in `worker_loop()`.

### Medium

- **Password reset**  
  “Forgot password” flow: request email → send reset link (signed token, short TTL) → form to set new password. Complements email verification.

- **Next run time on dashboard**  
  Show “Next run in X minutes” per user (or per casino) using `WEB_LOOP_INTERVAL_SEC` and last run time from DB or worker state.

- **Export run history**  
  Button or route to download history as CSV/JSON for the current user.

- **Configurable loop interval per user**  
  Allow each user to set “run every X hours” (within limits) instead of a single global `WEB_LOOP_INTERVAL_SEC`.

### Low

- **Notifications**  
  Optional email or webhook when a run fails repeatedly or when 2FA is required, so the user does not have to poll the dashboard.
- **Multiple Chrome profiles**  
  For power users, allow selecting a Chrome profile per user or per casino to isolate sessions.

---

## User flow (onboarding & journey)

Suggestions to make the path from signup → first successful run clear and predictable (web and Discord).

### High

- **First login: guided next step**  
  After signup or first login, show a clear “Get started” card or banner: e.g. “1. Add your Google login in Profile → 2. (Optional) Add casino credentials → 3. Start the loop or Run now.” Avoid dumping them on the dashboard with no context.

- **Block or warn “Start loop” when profile is empty**  
  If the user has no Google login set, either disable “Start loop” and show “Set Google login in Profile first,” or allow click but show a warning that runs will fail until credentials are set. Prevents “I started the loop but nothing happens.”

- **Explain “Run now” vs “Start loop”**  
  On the dashboard, add one line under each: e.g. “Run now = claim one casino right now. Start loop = automatically run all your casinos every X hours.” Reduces confusion about what each button does.

- **2FA: where to look and what happens on timeout**  
  When 2FA is required, the dashboard already shows the form; add a short line: “Check your phone/app for the code; if you don’t enter it in time, the run will stop and you can try again.” Optionally show a countdown (e.g. “Code expires in ~60s”) so they know to act quickly.

- **After “Run now”: what to expect**  
  After clicking “Run now”, show “Run started for [Casino]. Check Recent runs below for the result in a minute or two.” So they know to wait and where to look, instead of wondering if it worked.

### Medium

- **Empty state on dashboard**  
  When there are zero recent runs, the current “No runs yet…” is good; optionally add “Tip: add your Google login in Profile, then use Run now to test one casino.”

- **Profile: order and labels**  
  Make it obvious that Google is required for most casinos and casino credentials are for site-specific login. Consider a short “What’s this?” next to each section or a small help link.

- **History: what each status means**  
  In the History page (or in a tooltip), briefly explain: “success = claimed; error = something failed (see message); info = e.g. countdown or notice.” Helps users interpret results.

- **Discord: first-time flow**  
  In the Discord bot, after invite: pin a short message or reply to first `/help` with “1. Use `/profile set_google` in this channel 2. `/profile set_casino` for any site you use 3. `/start` to run the loop or `/universal <key>` to run one casino.” So Discord-only users get the same conceptual flow as web.

- **Error recovery: run failed**  
  When a run ends in “error” in history, consider adding a “Try again” or “Run again” link/button for that casino on the history or dashboard so they don’t have to re-select from the dropdown.

### Low

- **Post-signup redirect**  
  After signup, redirect to Profile instead of Dashboard with a one-time message: “Welcome. Add your Google login to get started.”
- **Progress indicator**  
  A simple “Setup: Google ✓, Casinos ✓, Ready to run” on dashboard so they see at a glance if they’re configured.
- **Discord: channel reminder**  
  If someone uses a profile or start command in the wrong channel, the embed could add: “Use this in the channel where the bot is allowed (e.g. #casino-claim).”

### High

- **Flash messages that persist once**  
  After redirect with `?msg=...` or `?error=...`, show the message and then replace the URL (e.g. with `history.replaceState`) so refreshing does not show the same message again.

- **Loading state for “Run now”**  
  Disable the button and show “Running…” after submit so the user knows the request was accepted and is in progress.

### Medium

- **Responsive layout**  
  Make dashboard, profile, and history readable and usable on small screens (stack cards, full-width forms, touch-friendly buttons).

- **Accessibility**  
  Ensure forms have correct labels, focus order, and contrast; add `aria-live` for success/error messages so screen readers announce them.

- **Profile: “keep password”**  
  For Google login, allow leaving the password field empty to mean “keep current”; only update when a new password is entered. Reduces re-typing.

### Low

- **Dark/light theme toggle**  
  Persist preference in cookie or localStorage and switch CSS variables.
- **Pagination for history**  
  Paginate or “load more” for run history instead of a single long list.

---

## Code quality

### High

- **Shared config loader**  
  `universal_casinoAPI.load_universal_casinos_config` and `web.worker.load_universal_config` both load `casinos_universal.json`. Centralize in one module and reuse so behavior and env (`UNIVERSAL_CASINOS_CONFIG`) are consistent.

- **Type hints**  
  Add type hints to `web/app.py` (request/response, form params), `web/database.py` (return types), and `web/worker.py` so mypy/IDE catch bugs and refactors are safer.

### Medium

- **Structured logging**  
  Use a single logger (e.g. `logging.getLogger(__name__)`) and log with levels (INFO/WARNING/ERROR) and optional JSON for production. Avoid ad-hoc `print` in new code.

- **Constants file**  
  Move magic numbers (e.g. session max age, limits, timeouts) and env key names into a small `web/config.py` (or similar) so tuning and documentation stay in one place.

- **Tests**  
  Add a minimal test suite: e.g. pytest for `database` (create user, profile, run history, 2FA), and one or two FastAPI TestClient tests for login and protected routes.

### Low

- **Lint/format**  
  Add ruff or black + isort to the repo and run in CI so style stays consistent.
- **Docstrings**  
  Add short docstrings to public functions in `web/` and `universal_casinoAPI` for maintainability.

---

## Ops & deployment

### High

- **Document production run**  
  In README or `web/README.md`, add a “Production” section: use gunicorn/uvicorn workers (e.g. `uvicorn web.app:app --workers 1 --host 0.0.0.0`), set `WEB_SECRET`, `WEB_COOKIE_SECURE=1`, HTTPS, and optionally reverse proxy (nginx). Mention that `python run_web.py` is for dev only.

- **Backup `web_data.db`**  
  Document or script periodic backups of SQLite (e.g. cron `cp web_data.db backups/web_data.db.$(date +%Y%m%d)` or `sqlite3 web_data.db ".backup backup.db"`). Optional: prune old run_history (e.g. keep last 90 days) to keep the file small.

### Medium

- **Docker image for web**  
  Add a Dockerfile (and optional compose) that runs only the web app (and worker) with Chrome/Chromium installed, so deploy is “build and run” without installing Python/Chrome on the host. Include Chrome driver and `WEB_WORKER_ENABLED=1` by default.

- **Log level from env**  
  Set `LOG_LEVEL=INFO` (or DEBUG) via env so production can turn on debug logs without code change. In `run_web.py` or app startup, call `logging.getLogger().setLevel(os.getenv("LOG_LEVEL", "INFO"))`.

- **Startup checks**  
  On startup, verify DB is writable, `casinos_universal.json` is loadable (if path set), and optionally that Chrome/driver is available when worker is enabled. Log clear errors instead of failing later in the first run.

### Low

- **Metrics**  
  Expose simple metrics (e.g. runs today, active users, loop on/off count) on `GET /metrics` (Prometheus) or `GET /api/stats` (JSON) for monitoring and dashboards.

- **Multi-instance**  
  Document that the in-process worker runs only on one instance; for horizontal scaling, run a single worker process or use a queue (e.g. Redis + Celery) so only one node runs Selenium.

- **Graceful reload**  
  Document SIGHUP/SIGTERM handling (e.g. uvicorn with `--reload` for dev vs no reload for prod) and that in-flight runs may be interrupted on deploy; consider “drain” mode that stops accepting new runs and waits for current run to finish.

---

## Documentation

### High

- **README: troubleshooting**  
  Add a short “Troubleshooting” section: e.g. “No casinos in dropdown” → check `casinos_universal.json` path and format; “Run never finishes” → check Chrome/Chromium and 2FA; “Loop does not run” → check `WEB_WORKER_ENABLED` and users with loop on.

- **Schema for `casinos_universal.json`**  
  Document required and optional keys (e.g. `key`, `name`, `base_url`, `google_btn_selectors`, `claim_selectors`, `interval_minutes`) and one full example so new casinos can be added without reading code.

### Medium

- **API overview**  
  List main HTTP routes (GET/POST) and JSON API endpoints with one-line descriptions so frontend or scripts can integrate without reading all of `app.py`.

- **Architecture diagram**  
  One-paragraph or simple diagram: browser → FastAPI → SQLite; worker loop → universal_casinoAPI + WebChannel → run_history and 2FA.

### Low

- **Contributing**  
  Short CONTRIBUTING.md: how to run locally, run tests, add a new casino (config-only vs new API), and submit a PR.
- **Changelog**  
  Keep a CHANGELOG.md or release notes for versioned releases.

---

## Already done (for reference)

- DISCORD_CHANNEL validation; profile encryption (Discord); rate limit on Discord profile commands.
- Discord: embeds, central channel check, default profile for loop, /profile list_casinos, /status, guild sync, logging.
- Web: safe config loader, worker keeps running without config, secure cookie option, 404 handler.
- Profile backup and audit log (Discord profiles.py).
- README and .env.example updates.

---

*Pick by priority (High first) or by theme (e.g. “Security only”) and tick off as you implement.*
