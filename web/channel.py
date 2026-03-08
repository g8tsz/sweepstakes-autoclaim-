# Casino Claim Web — Channel abstraction so automation can write to DB instead of Discord.

import asyncio
from typing import Any, Optional

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web import database as db


class WebChannel:
    """Implements a minimal 'channel' interface: send(embed=...) or send(content=...) writes to run_history."""

    def __init__(self, user_id: int, casino_key: str, run_id: Optional[str] = None):
        self.user_id = user_id
        self.casino_key = casino_key
        self.run_id = run_id or f"{user_id}_{casino_key}_{id(self)}"

    async def send(self, content: Optional[str] = None, embed: Any = None, file: Any = None, **kwargs):
        title = ""
        description = ""
        if embed is not None:
            if hasattr(embed, "title"):
                title = embed.title or ""
            if hasattr(embed, "description"):
                description = embed.description or ""
        if content:
            description = f"{description}\n{content}".strip() if description else content
        message = f"{title}: {description}".strip() if title else description
        status = "info"
        if "error" in message.lower() or "failed" in message.lower():
            status = "error"
        elif "claimed" in message.lower() or "success" in message.lower():
            status = "success"
        elif "2fa" in message.lower() or "2FA" in message:
            status = "2fa"
        db.add_run_history(self.user_id, self.casino_key, status, message[:500] if message else None)


async def wait_for_2fa_web(user_id: int, run_id: str, timeout_sec: int = 90) -> Optional[str]:
    """Poll DB until user submits 2FA code or timeout. Returns code or None."""
    elapsed = 0
    while elapsed < timeout_sec:
        code = db.get_2fa_code(user_id, run_id)
        if code:
            return code
        await asyncio.sleep(1)
        elapsed += 1
    return None
