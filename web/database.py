# Casino Claim Web — SQLite database and session handling.

import os
import json
import sqlite3
import hashlib
import secrets
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple

DB_PATH = os.getenv("WEB_DATABASE_PATH", "web_data.db")


def _get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db():
    conn = _get_conn()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS profiles (
                user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                google_login_encrypted TEXT,
                casino_credentials_json TEXT,
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS run_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                casino_key TEXT NOT NULL,
                status TEXT NOT NULL,
                message TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS loop_state (
                user_id INTEGER PRIMARY KEY REFERENCES users(id),
                enabled INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS pending_2fa (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                run_id TEXT NOT NULL,
                casino_name TEXT,
                code TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_run_history_user_created ON run_history(user_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_pending_2fa_user_run ON pending_2fa(user_id, run_id);
        """)
        conn.commit()
    finally:
        conn.close()


@contextmanager
def get_cursor():
    conn = _get_conn()
    try:
        cur = conn.cursor()
        yield cur
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------
def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}${h}"


def verify_password(password: str, stored: str) -> bool:
    if "$" not in stored:
        return False
    salt, h = stored.split("$", 1)
    return hashlib.sha256((salt + password).encode()).hexdigest() == h


def create_user(email: str, password: str) -> Optional[int]:
    with get_cursor() as cur:
        try:
            cur.execute(
                "INSERT INTO users (email, password_hash) VALUES (?, ?)",
                (email.strip().lower(), hash_password(password)),
            )
            uid = cur.lastrowid
            cur.execute("INSERT INTO profiles (user_id) VALUES (?)", (uid,))
            cur.execute("INSERT INTO loop_state (user_id, enabled) VALUES (?, 0)", (uid,))
            return uid
        except sqlite3.IntegrityError:
            return None


def get_user_by_email(email: str) -> Optional[Tuple[int, str]]:
    with get_cursor() as cur:
        cur.execute("SELECT id, password_hash FROM users WHERE email = ?", (email.strip().lower(),))
        row = cur.fetchone()
        return (row[0], row[1]) if row else None


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute("SELECT id, email, created_at FROM users WHERE id = ?", (user_id,))
        row = cur.fetchone()
        if not row:
            return None
        return {"id": row[0], "email": row[1], "created_at": row[2]}


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------
def get_profile(user_id: int) -> Dict[str, Any]:
    with get_cursor() as cur:
        cur.execute(
            "SELECT google_login_encrypted, casino_credentials_json FROM profiles WHERE user_id = ?",
            (user_id,),
        )
        row = cur.fetchone()
        if not row:
            return {}
        out = {}
        if row[0]:
            out["google_login"] = row[0]  # caller may decrypt
        if row[1]:
            try:
                out["casino"] = json.loads(row[1])
            except Exception:
                out["casino"] = {}
        return out


def set_google(user_id: int, google_login: str) -> None:
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO profiles (user_id, google_login_encrypted, updated_at) VALUES (?, ?, datetime('now')) "
            "ON CONFLICT(user_id) DO UPDATE SET google_login_encrypted = excluded.google_login_encrypted, updated_at = datetime('now')",
            (user_id, google_login),
        )


def set_casino_credentials(user_id: int, casino_credentials: Dict[str, str]) -> None:
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO profiles (user_id, casino_credentials_json, updated_at) VALUES (?, ?, datetime('now')) "
            "ON CONFLICT(user_id) DO UPDATE SET casino_credentials_json = excluded.casino_credentials_json, updated_at = datetime('now')",
            (user_id, json.dumps(casino_credentials)),
        )


def get_google_credentials(user_id: int) -> Optional[Tuple[str, str]]:
    prof = get_profile(user_id)
    raw = prof.get("google_login") or ""
    if not raw or ":" not in raw:
        return None
    parts = raw.split(":", 1)
    return (parts[0].strip(), parts[1].strip())


def get_casino_credentials(user_id: int) -> Dict[str, str]:
    prof = get_profile(user_id)
    return prof.get("casino") or {}


# ---------------------------------------------------------------------------
# Loop state
# ---------------------------------------------------------------------------
def set_loop_enabled(user_id: int, enabled: bool) -> None:
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO loop_state (user_id, enabled, updated_at) VALUES (?, ?, datetime('now')) "
            "ON CONFLICT(user_id) DO UPDATE SET enabled = excluded.enabled, updated_at = datetime('now')",
            (user_id, 1 if enabled else 0),
        )


def get_loop_enabled(user_id: int) -> bool:
    with get_cursor() as cur:
        cur.execute("SELECT enabled FROM loop_state WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        return bool(row and row[0])


def get_users_with_loop_enabled() -> List[int]:
    with get_cursor() as cur:
        cur.execute("SELECT user_id FROM loop_state WHERE enabled = 1")
        return [r[0] for r in cur.fetchall()]


# ---------------------------------------------------------------------------
# Run history
# ---------------------------------------------------------------------------
def add_run_history(user_id: int, casino_key: str, status: str, message: Optional[str] = None) -> int:
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO run_history (user_id, casino_key, status, message) VALUES (?, ?, ?, ?)",
            (user_id, casino_key, status, message or ""),
        )
        return cur.lastrowid


def get_run_history(user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute(
            "SELECT id, casino_key, status, message, created_at FROM run_history WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        )
        return [
            {"id": r[0], "casino_key": r[1], "status": r[2], "message": r[3], "created_at": r[4]}
            for r in cur.fetchall()
        ]


# ---------------------------------------------------------------------------
# Pending 2FA
# ---------------------------------------------------------------------------
def create_pending_2fa(user_id: int, run_id: str, casino_name: str = "") -> int:
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO pending_2fa (user_id, run_id, casino_name, code) VALUES (?, ?, ?, NULL)",
            (user_id, run_id, casino_name),
        )
        return cur.lastrowid


def set_2fa_code(user_id: int, run_id: str, code: str) -> bool:
    with get_cursor() as cur:
        cur.execute(
            "UPDATE pending_2fa SET code = ? WHERE user_id = ? AND run_id = ? AND code IS NULL",
            (code.strip(), user_id, run_id),
        )
        return cur.rowcount > 0


def get_2fa_code(user_id: int, run_id: str) -> Optional[str]:
    with get_cursor() as cur:
        cur.execute("SELECT code FROM pending_2fa WHERE user_id = ? AND run_id = ?", (user_id, run_id))
        row = cur.fetchone()
        return row[0] if row and row[0] else None


def get_pending_2fa_for_user(user_id: int) -> Optional[Dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute(
            "SELECT id, run_id, casino_name, created_at FROM pending_2fa WHERE user_id = ? AND code IS NULL ORDER BY created_at DESC LIMIT 1",
            (user_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {"id": row[0], "run_id": row[1], "casino_name": row[2], "created_at": row[3]}


def clear_pending_2fa(user_id: int, run_id: str) -> None:
    with get_cursor() as cur:
        cur.execute("DELETE FROM pending_2fa WHERE user_id = ? AND run_id = ?", (user_id, run_id))
