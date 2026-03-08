# Casino Claim Web — Session auth (signed cookie).

import os
import hashlib
import hmac
import json
import base64
from typing import Optional

from fastapi import Request, Response
from fastapi.responses import RedirectResponse

SECRET = os.getenv("WEB_SECRET", "change-me-in-production")
COOKIE_NAME = "casino_claim_session"
MAX_AGE = 86400 * 30  # 30 days


def _sign(data: str) -> str:
    return hmac.new(SECRET.encode(), data.encode(), hashlib.sha256).hexdigest()


def set_session(response: Response, user_id: int) -> None:
    payload = json.dumps({"user_id": user_id})
    b64 = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    sig = _sign(b64)
    value = f"{b64}.{sig}"
    response.set_cookie(COOKIE_NAME, value, max_age=MAX_AGE, httponly=True, samesite="lax")


def get_session(request: Request) -> Optional[int]:
    val = request.cookies.get(COOKIE_NAME)
    if not val or "." not in val:
        return None
    b64, sig = val.rsplit(".", 1)
    if hmac.compare_digest(_sign(b64), sig) is False:
        return None
    try:
        payload = base64.urlsafe_b64decode(b64 + "==").decode()
        data = json.loads(payload)
        return int(data.get("user_id", 0)) or None
    except Exception:
        return None


def clear_session(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME)


def require_user(request: Request) -> Optional[int]:
    return get_session(request)
