# Drake Hooks
# Casino Claim 2
# Per-user profile store for Google and casino credentials (slash /profile).
# Optional encryption, daily backup, and audit logging.

import os
import json
import datetime as dt
from typing import Any, Dict, Optional, Tuple

PROFILE_PATH = os.getenv("USER_PROFILES_PATH", "user_profiles.json")
PROFILE_ENCRYPTION_KEY = (os.getenv("PROFILE_ENCRYPTION_KEY") or "").strip()
PROFILE_AUDIT_LOG = (os.getenv("PROFILE_AUDIT_LOG") or "").strip()
_Fernet = None
if PROFILE_ENCRYPTION_KEY:
    try:
        from cryptography.fernet import Fernet
        _Fernet = Fernet
    except Exception:
        pass


def _encrypt(data: str) -> str:
    if not _Fernet or not PROFILE_ENCRYPTION_KEY:
        return data
    try:
        f = _Fernet(PROFILE_ENCRYPTION_KEY.encode() if isinstance(PROFILE_ENCRYPTION_KEY, str) else PROFILE_ENCRYPTION_KEY)
        return f.encrypt(data.encode()).decode()
    except Exception:
        return data


def _decrypt(data: str) -> str:
    if not _Fernet or not PROFILE_ENCRYPTION_KEY:
        return data
    try:
        f = _Fernet(PROFILE_ENCRYPTION_KEY.encode() if isinstance(PROFILE_ENCRYPTION_KEY, str) else PROFILE_ENCRYPTION_KEY)
        return f.decrypt(data.encode()).decode()
    except Exception:
        return data


def _audit(user_id: int, action: str, detail: str = "") -> None:
    if not PROFILE_AUDIT_LOG:
        return
    try:
        with open(PROFILE_AUDIT_LOG, "a", encoding="utf-8") as f:
            f.write(f"{dt.datetime.now(dt.timezone.utc).isoformat()} user_id={user_id} action={action} {detail}\n")
    except Exception:
        pass


def _load_raw() -> str:
    if not os.path.isfile(PROFILE_PATH):
        return "{}"
    try:
        with open(PROFILE_PATH, "r", encoding="utf-8") as f:
            raw = f.read()
        if _Fernet and PROFILE_ENCRYPTION_KEY:
            try:
                raw = _decrypt(raw)
            except Exception:
                pass  # file may be plain JSON from before encryption was enabled
        return raw
    except Exception:
        return "{}"


def _load() -> Dict[str, Any]:
    raw = _load_raw()
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _write_backup_once_per_day() -> None:
    """Write a timestamped backup file at most once per calendar day."""
    if not os.path.isfile(PROFILE_PATH):
        return
    today = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d")
    backup_path = f"{PROFILE_PATH}.backup.{today}"
    if os.path.isfile(backup_path):
        return
    try:
        raw = _load_raw()
        with open(backup_path, "w", encoding="utf-8") as f:
            f.write(raw)
    except Exception:
        pass


def _save_internal(data: Dict[str, Any]) -> None:
    raw = json.dumps(data, indent=2)
    if _Fernet and PROFILE_ENCRYPTION_KEY:
        raw = _encrypt(raw)
    with open(PROFILE_PATH, "w", encoding="utf-8") as f:
        f.write(raw)


def _save(data: Dict[str, Any]) -> None:
    _write_backup_once_per_day()
    _save_internal(data)


def _user_key(user_id: int) -> str:
    return str(user_id)


def get_profile(user_id: int) -> Dict[str, Any]:
    data = _load()
    return data.get(_user_key(user_id), {})


def set_google(user_id: int, email: str, password: str) -> None:
    data = _load()
    key = _user_key(user_id)
    if key not in data:
        data[key] = {}
    data[key]["google_login"] = f"{email}:{password}"
    _save(data)
    _audit(user_id, "set_google", "email_set")


def set_casino(user_id: int, casino_name: str, credentials: str) -> None:
    data = _load()
    key = _user_key(user_id)
    if key not in data:
        data[key] = {}
    if "casino" not in data[key]:
        data[key]["casino"] = {}
    data[key]["casino"][casino_name.upper().strip()] = credentials.strip()
    _save(data)
    _audit(user_id, "set_casino", f"casino={casino_name.upper().strip()}")


def clear_google(user_id: int) -> bool:
    data = _load()
    key = _user_key(user_id)
    if key not in data or "google_login" not in data[key]:
        return False
    del data[key]["google_login"]
    _save(data)
    _audit(user_id, "clear_google", "")
    return True


def clear_casino(user_id: int, casino_name: Optional[str] = None) -> bool:
    data = _load()
    key = _user_key(user_id)
    if key not in data or "casino" not in data[key]:
        return False
    if casino_name:
        cn = casino_name.upper().strip()
        if cn not in data[key]["casino"]:
            return False
        del data[key]["casino"][cn]
        _save(data)
        _audit(user_id, "clear_casino", f"casino={cn}")
    else:
        data[key]["casino"] = {}
        _save(data)
        _audit(user_id, "clear_casino", "all")
    return True


def clear_all(user_id: int) -> bool:
    data = _load()
    key = _user_key(user_id)
    if key not in data:
        return False
    del data[key]
    _save(data)
    _audit(user_id, "clear_all", "")
    return True


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
