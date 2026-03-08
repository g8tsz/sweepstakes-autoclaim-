# Casino Claim Web — Build Chrome driver for automation (no Discord dependency).

import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import SessionNotCreatedException
from webdriver_manager.chrome import ChromeDriverManager


def build_driver():
    opts = Options()
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--no-first-run")
    opts.add_argument("--no-default-browser-check")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-notifications")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--ignore-certificate-errors")
    ua = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
    )
    opts.add_argument(f"--user-agent={ua}")
    opts.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    instance_dir = os.getenv("CHROME_INSTANCE_DIR", "").strip() or os.getenv("CHROME_USER_DATA_DIR", "").strip()
    profile_dir = os.getenv("CHROME_PROFILE_DIR", "Default").strip()
    if instance_dir:
        opts.add_argument(f"--user-data-dir={instance_dir}")
        opts.add_argument(f"--profile-directory={profile_dir}")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
