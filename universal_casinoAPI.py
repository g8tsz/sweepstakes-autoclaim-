# Drake Hooks
# Casino Claim 2
# Universal Casino API — config-driven flow for any casino with Google login.
# Add entries to casinos_universal.json to support new casinos without writing Python.

import os
import asyncio
import json
import datetime as dt
from typing import Any, Dict, List, Optional

import discord
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# Load Google auth helper when needed
def _get_google_creds():
    raw = os.getenv("GOOGLE_LOGIN")
    if not raw or ":" not in raw:
        return None, None
    parts = raw.split(":", 1)
    return (parts[0].strip(), parts[1].strip())


async def universal_casino_flow(
    driver,
    bot,
    channel,
    config: Dict[str, Any],
    ctx=None,
    wait_2fa_fn=None,
) -> bool:
    """
    Run generic claim flow for a casino defined in config.
    Config: name, base_url, login_url (optional), use_google_login (bool),
            google_btn_selectors (list of dicts with by/xpath or by/css), 
            claim_selectors (list), claim_url (optional), countdown_selector (optional).
    Returns True if something was claimed or countdown sent; False on skip/fail.
    """
    name = config.get("name", "Unknown")
    base_url = config.get("base_url", "").strip()
    login_url = (config.get("login_url") or base_url).strip()
    use_google_login = config.get("use_google_login", True)
    google_btn_selectors = config.get("google_btn_selectors") or []
    claim_selectors = config.get("claim_selectors") or []
    claim_url = (config.get("claim_url") or base_url).strip()
    countdown_selector = config.get("countdown_selector")
    wait_after_load = int(config.get("wait_after_load_sec", 8))

    if not base_url:
        try:
            await channel.send(embed=_embed(f"{name} — Config error", "No base_url in config.", 0xF59E0B))
        except Exception:
            pass
        return False

    try:
        # 1) Open login or base page
        driver.get(login_url)
        await asyncio.sleep(wait_after_load)

        # 2) Optional: click "Sign in with Google" so we land on Google OAuth (or use existing session)
        if use_google_login and google_btn_selectors:
            clicked_google = False
            for sel in google_btn_selectors:
                by = (sel.get("by") or "xpath").lower()
                value = sel.get("xpath") or sel.get("css") or sel.get("value") or ""
                if not value:
                    continue
                try:
                    if by == "css" or by == "css_selector":
                        elem = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, value))
                        )
                    else:
                        elem = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable((By.XPATH, value))
                        )
                    elem.click()
                    clicked_google = True
                    await asyncio.sleep(5)
                    break
                except Exception:
                    continue
            if clicked_google and "accounts.google.com" in (driver.current_url or ""):
                # Run Google auth (same as !auth google). Prefer per-user creds from config (e.g. /profile).
                from googleauthAPI import google_auth
                user_creds = config.get("_user_google")
                if user_creds and len(user_creds) == 2:
                    username, password = user_creds
                else:
                    username, password = _get_google_creds()
                if username and password:
                    await google_auth(ctx, driver, channel, (username, password), wait_2fa_fn=wait_2fa_fn)
                    await asyncio.sleep(3)
                else:
                    try:
                        await channel.send(embed=_embed(
                            f"{name} — Google login required",
                            "Set GOOGLE_LOGIN in .env or use `/profile set_google` and run again.",
                            0xF59E0B,
                        ))
                    except Exception:
                        pass
                    return False

        # 3) Navigate to claim page if different
        if claim_url and claim_url != driver.current_url:
            driver.get(claim_url)
            await asyncio.sleep(wait_after_load)

        # 4) Try to click a claim button
        claimed = False
        for sel in claim_selectors:
            by = (sel.get("by") or "xpath").lower()
            value = sel.get("xpath") or sel.get("css") or sel.get("value") or ""
            if not value:
                continue
            try:
                if by == "css" or by == "css_selector":
                    elem = WebDriverWait(driver, 8).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, value))
                    )
                else:
                    elem = WebDriverWait(driver, 8).until(
                        EC.element_to_be_clickable((By.XPATH, value))
                    )
                elem.click()
                claimed = True
                try:
                    await channel.send(embed=_embed(f"{name} — Bonus claimed", "Daily bonus claimed.", 0x22C55E))
                except Exception:
                    pass
                await asyncio.sleep(2)
                break
            except Exception:
                continue

        if not claimed:
            # 5) Try to read countdown and send to Discord
            if countdown_selector:
                by = (countdown_selector.get("by") or "xpath").lower()
                value = countdown_selector.get("xpath") or countdown_selector.get("css") or countdown_selector.get("value") or ""
                if value:
                    try:
                        if by == "css" or by == "css_selector":
                            elem = WebDriverWait(driver, 6).until(
                                EC.presence_of_element_located((By.CSS_SELECTOR, value))
                            )
                        else:
                            elem = WebDriverWait(driver, 6).until(
                                EC.presence_of_element_located((By.XPATH, value))
                            )
                        text = (elem.text or "").strip()
                        if text:
                            try:
                                await channel.send(embed=_embed(f"{name} — Next bonus", text, 0x3B82F6))
                            except Exception:
                                pass
                            return True
                    except Exception:
                        pass
            # No claim, no countdown
            try:
                await channel.send(embed=_embed(f"{name} — No claim", "No claim button found (may not be ready).", 0xF59E0B))
            except Exception:
                pass

        return claimed
    except Exception as e:
        try:
            await channel.send(embed=_embed(f"{name} — Error", str(e)[:200], 0xEF4444))
        except Exception:
            pass
        return False


def _embed(title: str, description: str, color: int = 0x3B82F6) -> discord.Embed:
    e = discord.Embed(title=title, description=description, color=color)
    e.set_footer(text="Casino Claim")
    e.timestamp = dt.datetime.now(dt.timezone.utc)
    return e


def _is_google_login_casino(config: Dict[str, Any]) -> bool:
    """True only if this casino is configured for Google login (we only use these)."""
    if not config.get("use_google_login", False):
        return False
    selectors = config.get("google_btn_selectors") or []
    return len(selectors) > 0


def load_universal_casinos_config(path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Load list of universal casino configs from JSON file. Returns only casinos that support Google login."""
    if path is None:
        path = os.getenv("UNIVERSAL_CASINOS_CONFIG", "casinos_universal.json")
    if not os.path.isfile(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []
    if isinstance(data, list):
        raw = data
    elif isinstance(data, dict) and "casinos" in data:
        raw = data["casinos"]
    else:
        return []
    return [c for c in raw if _is_google_login_casino(c)]
