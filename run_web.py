#!/usr/bin/env python3
"""
Run the Casino Claim website. This is the main way to use the app: a full HTML site
with login, profile, dashboard (start/stop loop, run casino now), 2FA form, and history.

Requires: pip install -r requirements.txt
Then: python run_web.py
Open: http://localhost:8000

Optional .env: WEB_SECRET, WEB_DATABASE_PATH, WEB_WORKER_ENABLED=1, WEB_LOOP_INTERVAL_SEC
"""
import os
import sys

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    print(f"Starting Casino Claim website at http://{host}:{port}")
    print("Press Ctrl+C to stop.")
    uvicorn.run(
        "web.app:app",
        host=host,
        port=port,
        reload=os.getenv("RELOAD", "").lower() in ("1", "true", "yes"),
    )

if __name__ == "__main__":
    main()
