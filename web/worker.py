# Casino Claim Web — Background loop: run universal casinos for users with loop enabled.

import asyncio
import os
import time
import logging
from typing import Any, Dict, List

# Add project root for imports
import sys
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from web import database as db
from web.channel import WebChannel, wait_for_2fa_web

log = logging.getLogger(__name__)

# Default interval between full runs per user (seconds)
LOOP_INTERVAL_SEC = int(os.getenv("WEB_LOOP_INTERVAL_SEC", "7200"))  # 2h
TICK_SLEEP_SEC = 60

_driver = None


def get_driver():
    global _driver
    if _driver is None:
        from web.driver_builder import build_driver
        _driver = build_driver()
        log.info("Web worker: Chrome driver created.")
    return _driver


def load_universal_config() -> List[Dict[str, Any]]:
    from universal_casinoAPI import load_universal_casinos_config
    return load_universal_casinos_config()


async def run_one_casino_for_user(user_id: int, config: Dict[str, Any]) -> bool:
    """Run universal_casino_flow for one user and one casino config. Returns True if claimed or message sent."""
    key = (config.get("key") or config.get("name", "")).lower().replace(" ", "")
    name = config.get("name", key)
    run_id = f"run_{user_id}_{key}_{int(time.time())}"
    channel = WebChannel(user_id, key, run_id)

    async def wait_2fa_fn():
        db.create_pending_2fa(user_id, run_id, name)
        try:
            return await wait_for_2fa_web(user_id, run_id, 60)
        finally:
            db.clear_pending_2fa(user_id, run_id)

    run_config = dict(config)
    run_config["_user_google"] = db.get_google_credentials(user_id)
    driver = get_driver()
    try:
        from universal_casinoAPI import universal_casino_flow
        result = await universal_casino_flow(
            driver, None, channel, run_config, ctx=None, wait_2fa_fn=wait_2fa_fn
        )
        return result
    except Exception as e:
        log.exception("run_one_casino_for_user %s %s: %s", user_id, key, e)
        db.add_run_history(user_id, key, "error", str(e)[:300])
        return False


async def run_all_casinos_for_user(user_id: int, configs: List[Dict[str, Any]]) -> None:
    for cfg in configs:
        try:
            await run_one_casino_for_user(user_id, cfg)
        except Exception as e:
            log.warning("run_all_casinos_for_user %s: %s", user_id, e)
        await asyncio.sleep(5)


async def worker_loop():
    """Main loop: every TICK_SLEEP_SEC, check users with loop enabled and run their casinos if due."""
    configs = load_universal_config()
    if not configs:
        log.warning("Web worker: no universal casino configs loaded.")
        return
    last_run: Dict[int, float] = {}
    while True:
        try:
            users = db.get_users_with_loop_enabled()
            now = time.time()
            for user_id in users:
                last = last_run.get(user_id, 0)
                if now - last >= LOOP_INTERVAL_SEC:
                    log.info("Web worker: running casinos for user %s", user_id)
                    await run_all_casinos_for_user(user_id, configs)
                    last_run[user_id] = now
        except asyncio.CancelledError:
            break
        except Exception as e:
            log.exception("Web worker tick: %s", e)
        await asyncio.sleep(TICK_SLEEP_SEC)


_worker_task: asyncio.Task = None


def start_worker():
    global _worker_task
    if _worker_task is not None and not _worker_task.done():
        return
    _worker_task = asyncio.create_task(worker_loop())
    log.info("Web worker loop started.")


def stop_worker():
    global _worker_task
    if _worker_task is not None:
        _worker_task.cancel()
        _worker_task = None
        log.info("Web worker loop stopped.")
