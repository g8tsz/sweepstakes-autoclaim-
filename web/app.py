# Casino Claim Web — FastAPI application.

import os
import sys
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request, Response, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

# Project root
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from web import database as db
from web.auth import get_session, set_session, clear_session, require_user

# Optional: start worker in same process
from web.worker import worker_loop, start_worker, stop_worker, load_universal_config


def get_user_id(request: Request) -> Optional[int]:
    return get_session(request)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    if os.getenv("WEB_WORKER_ENABLED", "1") == "1":
        start_worker()
    yield
    stop_worker()


app = FastAPI(title="Casino Claim", lifespan=lifespan)
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

# Mount static if exists
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
class SignupBody(BaseModel):
    email: str
    password: str


class LoginBody(BaseModel):
    email: str
    password: str


class ProfileGoogleBody(BaseModel):
    email: str
    password: str


class ProfileCasinoBody(BaseModel):
    casino_name: str
    credentials: str


class TwoFABody(BaseModel):
    code: str


# ---------------------------------------------------------------------------
# Helpers for page data
# ---------------------------------------------------------------------------
def _dashboard_data(user_id: int):
    return {
        "loop_enabled": db.get_loop_enabled(user_id),
        "pending_2fa": db.get_pending_2fa_for_user(user_id),
        "recent_runs": db.get_run_history(user_id, limit=20),
        "universal_casino_count": len(load_universal_config()),
    }


def _casino_choices():
    configs = load_universal_config()
    keys = sorted(set((c.get("key") or c.get("name", "")).lower().replace(" ", "") for c in configs if (c.get("key") or c.get("name"))))
    known = keys + ["stake", "chanced", "fortunecoins", "modo", "crowncoins", "chumba", "globalpoker"]
    return sorted(set(k.upper() for k in known))


# ---------------------------------------------------------------------------
# Pages (HTML) — server-rendered with forms and buttons
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    user_id = get_user_id(request)
    if user_id is None:
        return RedirectResponse(url="/login", status_code=302)
    return RedirectResponse(url="/dashboard", status_code=302)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if get_user_id(request) is not None:
        return RedirectResponse(url="/dashboard", status_code=302)
    msg = request.query_params.get("msg")
    error = request.query_params.get("error")
    return templates.TemplateResponse("login.html", {"request": request, "msg": msg, "error": error})


@app.post("/login")
async def login_submit(request: Request, response: Response, email: str = Form(""), password: str = Form("")):
    if not email or not password:
        return RedirectResponse(url="/login?error=Email+and+password+required", status_code=302)
    row = db.get_user_by_email(email)
    if not row:
        return RedirectResponse(url="/login?error=Invalid+email+or+password", status_code=302)
    user_id, password_hash = row
    if not db.verify_password(password, password_hash):
        return RedirectResponse(url="/login?error=Invalid+email+or+password", status_code=302)
    set_session(response, user_id)
    return RedirectResponse(url="/dashboard", status_code=302)


@app.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    if get_user_id(request) is not None:
        return RedirectResponse(url="/dashboard", status_code=302)
    msg = request.query_params.get("msg")
    error = request.query_params.get("error")
    return templates.TemplateResponse("signup.html", {"request": request, "msg": msg, "error": error})


@app.post("/signup")
async def signup_submit(request: Request, response: Response, email: str = Form(""), password: str = Form("")):
    if not email or not password:
        return RedirectResponse(url="/signup?error=Email+and+password+required", status_code=302)
    if len(password) < 6:
        return RedirectResponse(url="/signup?error=Password+must+be+at+least+6+characters", status_code=302)
    user_id = db.create_user(email.strip(), password)
    if user_id is None:
        return RedirectResponse(url="/signup?error=Email+already+registered", status_code=302)
    set_session(response, user_id)
    return RedirectResponse(url="/dashboard", status_code=302)


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    user_id = get_user_id(request)
    if user_id is None:
        return RedirectResponse(url="/login", status_code=302)
    msg = request.query_params.get("msg")
    error = request.query_params.get("error")
    data = _dashboard_data(user_id)
    data["casino_choices"] = _casino_choices()
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "user_id": user_id, "msg": msg, "error": error, **data},
    )


@app.post("/loop/start")
async def page_loop_start(request: Request, response: Response):
    user_id = get_user_id(request)
    if user_id is None:
        return RedirectResponse(url="/login", status_code=302)
    db.set_loop_enabled(user_id, True)
    return RedirectResponse(url="/dashboard?msg=Loop+started", status_code=302)


@app.post("/loop/stop")
async def page_loop_stop(request: Request, response: Response):
    user_id = get_user_id(request)
    if user_id is None:
        return RedirectResponse(url="/login", status_code=302)
    db.set_loop_enabled(user_id, False)
    return RedirectResponse(url="/dashboard?msg=Loop+stopped", status_code=302)


@app.post("/run")
async def page_run_now(request: Request, response: Response, casino_key: str = Form(...)):
    user_id = get_user_id(request)
    if user_id is None:
        return RedirectResponse(url="/login", status_code=302)
    key = (casino_key or "").strip().lower().replace(" ", "")
    configs = load_universal_config()
    cfg = next((c for c in configs if (c.get("key") or c.get("name", "")).lower().replace(" ", "") == key), None)
    if not cfg:
        return RedirectResponse(url="/dashboard?error=Unknown+casino", status_code=302)
    from web.worker import run_one_casino_for_user
    import asyncio
    asyncio.create_task(run_one_casino_for_user(user_id, cfg))
    name = cfg.get("name", key)
    return RedirectResponse(url=f"/dashboard?msg=Run+started+for+{name.replace(' ', '+')}", status_code=302)


@app.post("/2fa")
async def page_submit_2fa(request: Request, response: Response, code: str = Form("")):
    user_id = get_user_id(request)
    if user_id is None:
        return RedirectResponse(url="/login", status_code=302)
    pending = db.get_pending_2fa_for_user(user_id)
    if not pending:
        return RedirectResponse(url="/dashboard?error=No+2FA+pending", status_code=302)
    if not (code or "").strip():
        return RedirectResponse(url="/dashboard?error=Code+required", status_code=302)
    ok = db.set_2fa_code(user_id, pending["run_id"], code.strip())
    if not ok:
        return RedirectResponse(url="/dashboard?error=Code+already+submitted+or+expired", status_code=302)
    return RedirectResponse(url="/dashboard?msg=2FA+submitted", status_code=302)


@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    user_id = get_user_id(request)
    if user_id is None:
        return RedirectResponse(url="/login", status_code=302)
    msg = request.query_params.get("msg")
    error = request.query_params.get("error")
    prof = db.get_profile(user_id)
    if prof.get("google_login"):
        parts = prof["google_login"].split(":", 1)
        prof["google_email"] = parts[0] if parts else ""
        prof["google_set"] = True
        del prof["google_login"]
    else:
        prof["google_email"] = ""
        prof["google_set"] = False
    prof["casino"] = prof.get("casino") or {}
    prof["casino_choices"] = _casino_choices()
    prof["casino_keys"] = list((prof.get("casino") or {}).keys())
    return templates.TemplateResponse(
        "profile.html",
        {"request": request, "user_id": user_id, "msg": msg, "error": error, "profile": prof},
    )


@app.post("/profile/google")
async def page_profile_google(request: Request, response: Response, email: str = Form(""), password: str = Form("")):
    user_id = get_user_id(request)
    if user_id is None:
        return RedirectResponse(url="/login", status_code=302)
    if not email or not password:
        return RedirectResponse(url="/profile?error=Email+and+password+required", status_code=302)
    db.set_google(user_id, f"{email.strip()}:{password}")
    return RedirectResponse(url="/profile?msg=Google+login+saved", status_code=302)


@app.post("/profile/casinos")
async def page_profile_casinos(
    request: Request, response: Response,
    casino_name: str = Form(""), credentials: str = Form(""),
):
    user_id = get_user_id(request)
    if user_id is None:
        return RedirectResponse(url="/login", status_code=302)
    name = (casino_name or "").strip().upper()
    if not name or not (credentials or "").strip():
        return RedirectResponse(url="/profile?error=Casino+name+and+credentials+required", status_code=302)
    creds = db.get_casino_credentials(user_id)
    creds[name] = credentials.strip()
    db.set_casino_credentials(user_id, creds)
    return RedirectResponse(url="/profile?msg=Casino+credentials+saved", status_code=302)


@app.get("/history", response_class=HTMLResponse)
async def history_page(request: Request):
    user_id = get_user_id(request)
    if user_id is None:
        return RedirectResponse(url="/login", status_code=302)
    runs = db.get_run_history(user_id, limit=50)
    return templates.TemplateResponse("history.html", {"request": request, "user_id": user_id, "runs": runs})


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
@app.post("/api/signup")
async def api_signup(body: SignupBody, response: Response):
    if not body.email or not body.password:
        raise HTTPException(status_code=400, detail="Email and password required")
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    user_id = db.create_user(body.email.strip(), body.password)
    if user_id is None:
        raise HTTPException(status_code=400, detail="Email already registered")
    set_session(response, user_id)
    return {"ok": True, "user_id": user_id}


@app.post("/api/login")
async def api_login(body: LoginBody, response: Response):
    row = db.get_user_by_email(body.email)
    if not row:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    user_id, password_hash = row
    if not db.verify_password(body.password, password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    set_session(response, user_id)
    return {"ok": True, "user_id": user_id}


@app.post("/api/logout")
async def api_logout(response: Response):
    clear_session(response)
    return RedirectResponse(url="/login", status_code=302)


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------
@app.get("/api/profile")
async def api_get_profile(request: Request):
    user_id = get_user_id(request)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not logged in")
    prof = db.get_profile(user_id)
    # Mask passwords
    if prof.get("google_login"):
        parts = prof["google_login"].split(":", 1)
        prof["google_email"] = parts[0] if parts else ""
        prof["google_set"] = True
        del prof["google_login"]
    else:
        prof["google_email"] = ""
        prof["google_set"] = False
    prof["casino"] = prof.get("casino") or {}
    return prof


@app.post("/api/profile/google")
async def api_set_google(request: Request, body: ProfileGoogleBody):
    user_id = get_user_id(request)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not logged in")
    if not body.email or not body.password:
        raise HTTPException(status_code=400, detail="Email and password required")
    db.set_google(user_id, f"{body.email.strip()}:{body.password}")
    return {"ok": True}


@app.post("/api/profile/casinos")
async def api_set_casino(request: Request, body: ProfileCasinoBody):
    user_id = get_user_id(request)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not logged in")
    name = (body.casino_name or "").strip().upper()
    if not name or not (body.credentials or "").strip():
        raise HTTPException(status_code=400, detail="Casino name and credentials required")
    creds = db.get_casino_credentials(user_id)
    creds[name] = body.credentials.strip()
    db.set_casino_credentials(user_id, creds)
    return {"ok": True}


@app.get("/api/profile/list_casinos")
async def api_list_casinos(request: Request):
    user_id = get_user_id(request)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not logged in")
    configs = load_universal_config()
    keys = sorted(set((c.get("key") or c.get("name", "")).lower().replace(" ", "") for c in configs if (c.get("key") or c.get("name"))))
    known = keys + ["STAKE", "CHANCED", "FORTUNECOINS", "MODO", "CROWNCOINS", "CHUMBA", "GLOBALPOKER"]
    return {"casinos": sorted(set(k.upper() for k in known))}


# ---------------------------------------------------------------------------
# Loop control
# ---------------------------------------------------------------------------
@app.post("/api/loop/start")
async def api_loop_start(request: Request):
    user_id = get_user_id(request)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not logged in")
    db.set_loop_enabled(user_id, True)
    return {"ok": True, "enabled": True}


@app.post("/api/loop/stop")
async def api_loop_stop(request: Request):
    user_id = get_user_id(request)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not logged in")
    db.set_loop_enabled(user_id, False)
    return {"ok": True, "enabled": False}


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------
@app.get("/api/status")
async def api_status(request: Request):
    user_id = get_user_id(request)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not logged in")
    enabled = db.get_loop_enabled(user_id)
    pending = db.get_pending_2fa_for_user(user_id)
    history = db.get_run_history(user_id, limit=20)
    configs = load_universal_config()
    return {
        "loop_enabled": enabled,
        "pending_2fa": pending,
        "recent_runs": history,
        "universal_casino_count": len(configs),
    }


# ---------------------------------------------------------------------------
# Run now
# ---------------------------------------------------------------------------
@app.post("/api/run/{casino_key}")
async def api_run_now(request: Request, casino_key: str):
    user_id = get_user_id(request)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not logged in")
    key = casino_key.strip().lower().replace(" ", "")
    configs = load_universal_config()
    cfg = next((c for c in configs if (c.get("key") or c.get("name", "")).lower().replace(" ", "") == key), None)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"Unknown casino: {casino_key}")
    # Run in background (same process)
    from web.worker import run_one_casino_for_user
    import asyncio
    asyncio.create_task(run_one_casino_for_user(user_id, cfg))
    return {"ok": True, "message": f"Run started for {cfg.get('name', key)}"}


# ---------------------------------------------------------------------------
# 2FA
# ---------------------------------------------------------------------------
@app.get("/api/2fa")
async def api_get_2fa(request: Request):
    user_id = get_user_id(request)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not logged in")
    pending = db.get_pending_2fa_for_user(user_id)
    return {"pending": pending}


@app.post("/api/2fa")
async def api_submit_2fa(request: Request, body: TwoFABody):
    user_id = get_user_id(request)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not logged in")
    pending = db.get_pending_2fa_for_user(user_id)
    if not pending:
        raise HTTPException(status_code=400, detail="No 2FA pending")
    run_id = pending["run_id"]
    if not (body.code or "").strip():
        raise HTTPException(status_code=400, detail="Code required")
    ok = db.set_2fa_code(user_id, run_id, body.code.strip())
    if not ok:
        raise HTTPException(status_code=400, detail="Code already submitted or expired")
    return {"ok": True}
