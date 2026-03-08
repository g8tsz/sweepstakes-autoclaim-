# Suggestions for Casino Claim Bot

Review notes and improvement ideas. Tick off as you implement.

---

## Critical / Security

- [x] **DISCORD_CHANNEL validation** — If `DISCORD_CHANNEL` is empty or non-numeric, `int(os.getenv(...))` raises and the bot crashes on startup. Use a try/except and fail fast with a clear message or skip channel checks when not set. *(Done: safe parsing, fallback to 0, log warning.)*
- [x] **Profile storage** — Optional encryption via `PROFILE_ENCRYPTION_KEY` (Fernet). README documents file permissions and encryption. *(Done: profiles.py encrypts/decrypts when key set; cryptography optional.)*
- [x] **Rate limiting** — `/profile set_google` and `set_casino` limited to `PROFILE_RATE_LIMIT_PER_MINUTE` (default 5) per user. *(Done.)*

---

## Consistency & UX

- [x] **Channel messages as embeds** — Universal flow and `googleauthAPI` send Discord embeds with themed colors. *(Done.)*
- [x] **! commands** — `!start`, `!stop`, `!help` and prevent_manual reply with embeds. *(Done.)*
- [x] **2FA / Google auth** — `wait_for_2fa(site_name, timeout, channel=None)` sends embed when channel provided; timeout/success follow-up embeds. *(Done.)*

---

## Features

- [x] **Default profile for loop** — `DEFAULT_PROFILE_USER_ID` env var; loop uses that user’s `/profile` Google creds for universal casinos. *(Done.)*
- [x] **/profile list_casinos** — Subcommand lists known casino names for `set_casino`. *(Done.)*
- [x] **Slash command for status** — `/status` returns embed: loop running, next run times, universal casino count. *(Done.)*
- [x] **Guild sync for slash** — `DISCORD_GUILD_ID` env; when set, `on_ready` syncs to that guild for faster updates. *(Done.)*

---

## Code Quality

- [x] **DesiredCapabilities** — Removed; use `Options().set_capability("goog:loggingPrefs", ...)` only. *(Done.)*
- [x] **Centralize channel check** — Slash commands use shared `_slash_channel_check()` and `_slash_channel_fail()`. *(Done.)*
- [ ] **Type hints** — Add type hints to `embed_message` (e.g. `List[dict]` for fields) and to slash handlers for clarity. *(Optional.)*
- [x] **Logging** — Replaced `print()` with `logging` (log.info, log.warning, log.exception). *(Done.)*

---

## Docs & Ops

- [x] **README** — Security section: protect `.env` and `user_profiles.json`, encryption, audit log. *(Done.)*
- [x] **.env.example** — `DEFAULT_PROFILE_USER_ID`, `USER_PROFILES_PATH`, `DISCORD_GUILD_ID`, `PROFILE_ENCRYPTION_KEY`, `PROFILE_AUDIT_LOG`, `PROFILE_RATE_LIMIT_PER_MINUTE`; note sensitive data. *(Done.)*

---

## Optional

- [x] **Backup profiles** — Timestamped backup `user_profiles.json.backup.YYYYMMDD` once per calendar day before overwrite. *(Done.)*
- [x] **Audit log** — `PROFILE_AUDIT_LOG` file path logs user id + action (no credentials) on set/clear. *(Done.)*
