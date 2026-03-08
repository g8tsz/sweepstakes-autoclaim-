# Drake Hooks
# Casino Claim 2
# Never Miss a Casino Bonus Again! A discord app for claiming social casino bonuses.

import os
import glob
import re
import time
import logging
import discord
import asyncio
import importlib
from dataclasses import dataclass, field
import datetime as dt
from typing import Awaitable, Callable, List, Optional

from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ───────────────────────────────────────────────────────────
# Selenium / Chrome
# ───────────────────────────────────────────────────────────
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import SessionNotCreatedException

# Discord
from discord import Intents
from discord.ext import commands
from discord import app_commands

# (other modules may use these; imports are harmless here)
import undetected_chromedriver as uc  # noqa: F401

from concurrent.futures import ThreadPoolExecutor
_executor = ThreadPoolExecutor(max_workers=4)

import threading
_active_exec_jobs = 0
_active_exec_lock = threading.Lock()

def _exec_job_started():
    global _active_exec_jobs
    with _active_exec_lock:
        _active_exec_jobs += 1

def _exec_job_finished():
    global _active_exec_jobs
    with _active_exec_lock:
        _active_exec_jobs = max(0, _active_exec_jobs - 1)



# ───────────────────────────────────────────────────────────
# Dynamic API imports (missing modules are OK)
# ───────────────────────────────────────────────────────────
api_modules = [
    "fortunewheelzAPI",
    "fortunecoinsAPI",
    "americanluckAPI",
    "stakeAPI",
    "modoAPI",
    "googleauthAPI",
    "chancedAPI",
    "rollingrichesAPI",
    "jefebetAPI",
    "spinpalsAPI",
    "spinquestAPI",
    "funrizeAPI",
    "realprizeAPI",
    "globalpokerAPI",
    "dingdingdingAPI",
    "chumbaAPI",
    "crowncoinsAPI",
    "zulaAPI",
    "luckybirdAPI",
    "sportzinoAPI",
    "nolimitcoinsAPI",
    "smilescasinoAPI",
    "jumboAPI",
    "yaycasinoAPI",
    "luckylandAPI",
]
for module_name in api_modules:
    try:
        module = importlib.import_module(module_name)
        globals().update(vars(module))
    except Exception as e:
        log.warning("Failed to import %s: %s", module_name, e)

# ───────────────────────────────────────────────────────────
# Env & Discord setup
# ───────────────────────────────────────────────────────────
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
_raw_channel = (os.getenv("DISCORD_CHANNEL") or "").strip()
try:
    DISCORD_CHANNEL = int(_raw_channel) if _raw_channel else 0
except ValueError:
    DISCORD_CHANNEL = 0
if not DISCORD_CHANNEL and DISCORD_TOKEN:
    log.warning("DISCORD_CHANNEL is missing or invalid; slash commands may allow all channels.")

intents = Intents.default()
intents.message_content = True

# ───────────────────────────────────────────────────────────
# Selenium driver (headed; Xvfb is started by entrypoint.sh)
# ───────────────────────────────────────────────────────────
options = Options()
options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

instance_dir = os.getenv("CHROME_INSTANCE_DIR", "").strip()
profile_dir = os.getenv("CHROME_PROFILE_DIR", "Default").strip()

def _clean_chrome_locks(root: str, profile: str) -> None:
    """Delete Chrome lock files that make Chrome think the profile is in use."""
    try:
        for pat in ("Singleton*",):
            for p in glob.glob(os.path.join(root, pat)):
                try:
                    os.remove(p)
                except Exception:
                    pass
        prof_path = os.path.join(root, profile)
        os.makedirs(prof_path, exist_ok=True)
        for pat in ("Singleton*", "LOCK", "LOCKFILE", "Safe Browsing*"):
            for p in glob.glob(os.path.join(prof_path, pat)):
                try:
                    os.remove(p)
                except Exception:
                    pass
        for p in ("DevToolsActivePort",):
            fp = os.path.join(prof_path, p)
            if os.path.exists(fp):
                try:
                    os.remove(fp)
                except Exception:
                    pass
    except Exception:
        pass

def _apply_common_chrome_flags(opts: Options) -> None:
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--hide-crash-restore-bubble")
    opts.add_argument("--no-first-run")
    opts.add_argument("--no-default-browser-check")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-notifications")
    opts.add_argument("--allow-geolocation")
    opts.add_argument("--enable-third-party-cookies")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--disable-features=DisableLoadExtensionCommandLineSwitch")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--ignore-certificate-errors")
    opts.add_argument("--ignore-ssl-errors")
    opts.add_argument("disable-infobars")
    opts.add_argument(f"--remote-debugging-port={9222 + (os.getpid() % 1000)}")
    ua = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36")
    opts.add_argument(f"--user-agent={ua}")

# Persistent profile (prefer CHROME_INSTANCE_DIR)
if instance_dir:
    log.info("Chrome profile root: %s  profile dir: %s", instance_dir, profile_dir)
    _clean_chrome_locks(instance_dir, profile_dir)
    options.add_argument(f"--user-data-dir={instance_dir}")
    options.add_argument(f"--profile-directory={profile_dir}")
else:
    user_data_root = os.getenv("CHROME_USER_DATA_DIR", "").strip()
    if user_data_root:
        log.info("Chrome profile root: %s  profile dir: %s", user_data_root, profile_dir)
        _clean_chrome_locks(user_data_root, profile_dir)
        options.add_argument(f"--user-data-dir={user_data_root}")
        options.add_argument(f"--profile-directory={profile_dir}")
    else:
        log.info("Chrome: no persistent profile configured (ephemeral session).")

# Optional CRX
crx_path = "/temp/CAPTCHA-Solver-auto-hCAPTCHA-reCAPTCHA-freely-Chrome-Web-Store.crx"
if os.path.exists(crx_path):
    options.add_extension(crx_path)

_apply_common_chrome_flags(options)

def _build_driver_with_retry(opts: Options):
    """Create the Chrome driver; if Chrome says 'profile in use', force-unlock and retry once."""
    try:
        return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
    except SessionNotCreatedException as e:
        msg = str(e)
        if "user data directory is already in use" in msg:
            root = instance_dir or os.getenv("CHROME_USER_DATA_DIR", "").strip()
            prof = profile_dir
            if root:
                log.info("Chrome: retrying after force-unlock of profile.")
                _clean_chrome_locks(root, prof)
                time.sleep(1.0)
                return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
        raise

driver = _build_driver_with_retry(options)

# ───────────────────────────────────────────────────────────
# Discord bot + 2FA capture plumbing
# ───────────────────────────────────────────────────────────
bot = commands.Bot(command_prefix="!", intents=intents, case_insensitive=True)
bot.remove_command("help")

# Per-user profiles for /profile (Google + casino credentials)
import profiles as user_profiles

# Rate limit for /profile set_google and set_casino (per user, per minute)
PROFILE_RATE_LIMIT_PER_MINUTE = int(os.getenv("PROFILE_RATE_LIMIT_PER_MINUTE", "5"))
_profile_rate_ts: dict = {}
_profile_rate_lock = threading.Lock()

def _profile_rate_limit_check(user_id: int) -> bool:
    """Return True if user is over rate limit (should reject). On allow, records this request."""
    with _profile_rate_lock:
        now = time.time()
        key = str(user_id)
        if key not in _profile_rate_ts:
            _profile_rate_ts[key] = []
        cutoff = now - 60
        _profile_rate_ts[key] = [t for t in _profile_rate_ts[key] if t > cutoff]
        if len(_profile_rate_ts[key]) >= PROFILE_RATE_LIMIT_PER_MINUTE:
            return True
        _profile_rate_ts[key].append(now)
        return False

# Embed theme for slash commands (green, blue, amber, red)
EMBED_COLOR_SUCCESS = 0x22C55E
EMBED_COLOR_INFO    = 0x3B82F6
EMBED_COLOR_WARN    = 0xF59E0B
EMBED_COLOR_ERROR   = 0xEF4444

def embed_message(title: str, description: str = None, color: int = EMBED_COLOR_INFO, fields: List[dict] = None, footer: str = "Casino Claim") -> discord.Embed:
    e = discord.Embed(title=title, description=description or "", color=color)
    if fields:
        for f in fields:
            e.add_field(name=f.get("name", "\u200b"), value=f.get("value", "\u200b"), inline=f.get("inline", True))
    e.set_footer(text=footer)
    e.timestamp = dt.datetime.now(dt.timezone.utc)
    return e

bot.awaiting_2fa_for = None
bot.pending_2fa_code = None
bot._pending_2fa_event = asyncio.Event()

@bot.event
async def on_message(message: discord.Message):
    if message.channel.id == DISCORD_CHANNEL:
        text = message.content.strip()
        if text.isdigit() and 5 <= len(text) <= 8:
            if getattr(bot, "awaiting_2fa_for", None):
                bot.pending_2fa_code = text
                try:
                    bot._pending_2fa_event.set()
                except Exception:
                    bot._pending_2fa_event = asyncio.Event()
                    bot._pending_2fa_event.set()
            else:
                bot.two_fa_code = text  # legacy fallback
                log.info("2FA: stored code (legacy)")
    await bot.process_commands(message)

async def wait_for_2fa(site_name: str, timeout: int = 90, channel: Optional[discord.abc.Messageable] = None) -> Optional[str]:
    if bot.awaiting_2fa_for:
        return None
    bot.awaiting_2fa_for = site_name
    bot.pending_2fa_code = None
    bot._pending_2fa_event = asyncio.Event()
    if channel:
        try:
            emb = embed_message("2FA required", f"Reply in this channel with your **{site_name}** 2FA code (5–8 digits) within {timeout}s.", EMBED_COLOR_WARN)
            await channel.send(embed=emb)
        except Exception:
            pass
    try:
        await asyncio.wait_for(bot._pending_2fa_event.wait(), timeout=timeout)
    except asyncio.TimeoutError:
        code = None
        if channel:
            try:
                await channel.send(embed=embed_message("2FA timeout", f"No 2FA code received for **{site_name}** in time.", EMBED_COLOR_ERROR))
            except Exception:
                pass
    else:
        code = bot.pending_2fa_code
        if channel and code:
            try:
                await channel.send(embed=embed_message("2FA received", f"Code received for **{site_name}**.", EMBED_COLOR_SUCCESS))
            except Exception:
                pass
    bot.awaiting_2fa_for = None
    bot.pending_2fa_code = None
    bot._pending_2fa_event = asyncio.Event()
    return code

# ───────────────────────────────────────────────────────────
# Loop runner with hard per-casino timeouts
# ───────────────────────────────────────────────────────────
@dataclass
class CasinoLoopEntry:
    key: str
    display_name: str
    runner: Callable[[discord.abc.Messageable], Awaitable[None]]
    interval_minutes: float
    next_run: dt = field(default_factory=lambda: dt.datetime.now(dt.timezone.utc))

    def schedule_next(self):
        self.next_run = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=self.interval_minutes)


# constants for main loop. change as you see fit or run !config in discord.
LOOP_STAGGER_SECONDS = 30
PER_CASINO_TIMEOUT_SEC = int(os.getenv("CASINO_TIMEOUT_SECONDS", "500"))  
MAIN_TICK_SLEEP = 10

async def _run_luckybird(channel):      await luckybird_entry(None, driver, bot, channel)
async def _run_zula(channel):           await zula_uc(None, channel)
async def _run_sportzino(channel):      await Sportzino(None, driver, channel)
async def _run_nlc(channel):            await nolimitcoins_flow(None, driver, channel)
async def _run_funrize(channel):        await funrize_flow(None, driver, channel)
async def _run_globalpoker(channel):    await global_poker(None, driver, channel)
async def _run_jefebet(channel):        await jefebet_casino(None, driver, channel)
async def _run_crowncoins(channel):     await crowncoins_casino(driver, bot, None, channel)
async def _run_smilescasino(channel):   await smilescasino_casino(None, driver, channel)
async def _run_jumbo(channel):          await jumbo_casino(None, driver, channel)
async def _run_yaycasino(channel):      await yaycasino_uc(None, channel)
async def _run_realprize(channel):      await realprize_uc(None, channel)
async def _run_luckyland(channel):      await luckyland_uc(None, channel)


# Modo runner used by loop (claim → countdown)
async def _run_modo(channel):
    ok = await claim_modo_bonus(driver, bot, None, channel)
    if not ok:
        await check_modo_countdown(driver, bot, None, channel)

async def _run_rollingriches(channel):  await rolling_riches_casino(None, driver, channel)
async def _run_stake(channel):          await stake_claim(driver, bot, None, channel)
async def _run_fortunewheelz(channel):  await fortunewheelz_flow(None, driver, channel)
async def _run_spinquest(channel):      await spinquest_flow(None, driver, channel)
async def _run_americanluck(channel):   await americanluck_uc(None, channel)
async def _run_fortunecoins(channel):
    loop = asyncio.get_running_loop()
    from fortunecoinsAPI import fortunecoins_uc_blocking
    _exec_job_started()
    try:
        await loop.run_in_executor(_executor, fortunecoins_uc_blocking, bot, channel.id, loop)
    finally:
        _exec_job_finished()

casino_loop_entries: List[CasinoLoopEntry] = [
    CasinoLoopEntry("luckybird",     "LuckyBird",         _run_luckybird,       120),
    CasinoLoopEntry("globalpoker",   "GlobalPoker",       _run_globalpoker,     120),
    CasinoLoopEntry("jefebet",       "JefeBet",           _run_jefebet,         120),
    CasinoLoopEntry("spinquest",     "SpinQuest",         _run_spinquest,       120),
    CasinoLoopEntry("jumbo",         "Jumbo",             _run_jumbo,           120),
    CasinoLoopEntry("fortunewheelz", "Fortune Wheelz",    _run_fortunewheelz,   120),
    CasinoLoopEntry("nolimitcoins",  "NoLimitCoins",      _run_nlc,             120),

    # Enable when you want Modo and Stake in the loop cadence:
    # CasinoLoopEntry("modo",          "Modo",              _run_modo,            120),
    # CasinoLoopEntry("stake",         "Stake",             _run_stake,           120),

    # 24h cadence group (no countdown/problematic)
    # CasinoLoopEntry("realprize",     "RealPrize",         _run_realprize,       1440),
    CasinoLoopEntry("funrize",       "Funrize",           _run_funrize,         1440),
    CasinoLoopEntry("rollingriches", "Rolling Riches",    _run_rollingriches,   1440),
    CasinoLoopEntry("americanluck",  "American Luck",      _run_americanluck,   1440),
    CasinoLoopEntry("fortunecoins",  "Fortune Coins",     _run_fortunecoins,    1440),
    CasinoLoopEntry("zula",          "Zula Casino",       _run_zula,            1440),
    CasinoLoopEntry("sportzino",     "Sportzino",         _run_sportzino,       1440),
    CasinoLoopEntry("yaycasino",     "YayCasino",         _run_yaycasino,       1440),
    # CasinoLoopEntry("smilescasino",  "Smiles Casino",     _run_smilescasino,    1440),
    # CasinoLoopEntry("luckyland",     "LuckyLand",         _run_luckyland,       1440),

]

# Universal casinos (config-driven from casinos_universal.json; Google login)
UNIVERSAL_CASINO_KEYS: List[str] = []
try:
    from universal_casinoAPI import universal_casino_flow, load_universal_casinos_config
    _universal_configs = load_universal_casinos_config()
    for cfg in _universal_configs:
        key = (cfg.get("key") or cfg.get("name", "")).lower().replace(" ", "")
        if not key:
            continue
        display = cfg.get("name", key)
        interval = float(cfg.get("interval_minutes", 1440))
        UNIVERSAL_CASINO_KEYS.append(key)

        def _make_universal_runner(config_copy):
            async def _run(channel):
                run_config = dict(config_copy)
                default_uid = (os.getenv("DEFAULT_PROFILE_USER_ID") or "").strip()
                if default_uid:
                    try:
                        uid_int = int(default_uid)
                        creds = user_profiles.get_google_credentials(uid_int)
                        if creds:
                            run_config["_user_google"] = creds
                    except Exception:
                        pass
                return await universal_casino_flow(driver, bot, channel, run_config, None)
            return _run

        casino_loop_entries.append(
            CasinoLoopEntry(key, display, _make_universal_runner(dict(cfg)), interval)
        )
    if _universal_configs:
        log.info("Universal: loaded %s casino(s) from config.", len(_universal_configs))
except Exception as e:
    log.warning("Universal: failed to load config: %s", e)

def reset_loop_schedule():
    base = dt.datetime.now(dt.timezone.utc)
    for i, entry in enumerate(casino_loop_entries):
        entry.next_run = base + dt.timedelta(seconds=i * LOOP_STAGGER_SECONDS)

main_loop_task: Optional[asyncio.Task] = None
main_loop_running = False

def is_main_loop_running() -> bool:
    return main_loop_running and main_loop_task and not main_loop_task.done()

async def run_main_loop(channel: discord.abc.Messageable):
    global main_loop_running
    try:
        while main_loop_running:
            now = dt.datetime.now(dt.timezone.utc)
            for entry in casino_loop_entries:
                if now >= entry.next_run:
                    try:
                        await asyncio.wait_for(entry.runner(channel), timeout=PER_CASINO_TIMEOUT_SEC)
                    except asyncio.TimeoutError:
                        try:
                            await channel.send(embed=embed_message(f"{entry.display_name} — Timeout", f"Timed out after {PER_CASINO_TIMEOUT_SEC}s. Skipping.", EMBED_COLOR_WARN))
                        except Exception:
                            pass
                        log.warning("Loop: %s timed out.", entry.display_name)
                    except Exception as e:
                        log.warning("Loop: error in %s: %s", entry.display_name, e)
                    finally:
                        entry.schedule_next()
            await asyncio.sleep(MAIN_TICK_SLEEP)
    except asyncio.CancelledError:
        pass
    finally:
        main_loop_running = False

async def start_main_loop(channel: Optional[discord.abc.Messageable] = None) -> bool:
    global main_loop_task, main_loop_running
    if is_main_loop_running():
        return False
    if channel is None:
        channel = bot.get_channel(DISCORD_CHANNEL)
    if channel is None:
        log.warning("Loop: cannot start, channel not found.")
        return False
    reset_loop_schedule()
    main_loop_running = True
    main_loop_task = asyncio.create_task(run_main_loop(channel))
    return True

async def stop_main_loop() -> bool:
    global main_loop_task, main_loop_running
    if not is_main_loop_running():
        return False
    main_loop_running = False
    if main_loop_task:
        main_loop_task.cancel()
        try:
            await main_loop_task
        except asyncio.CancelledError:
            pass
    main_loop_task = None
    return True

# ───────────────────────────────────────────────────────────
# Modo auth maintenance (only when loop is STOPPED)
# ───────────────────────────────────────────────────────────
# REFRESH_CHECK_MINUTES = int(os.getenv("MODO_REFRESH_CHECK_MINUTES", "60"))
# modo_auth_lock = asyncio.Lock()  # serialize all modo auth attempts

# async def run_modo_auth(channel):
#     """Serialize calls to modoAPI.authenticate_modo to avoid concurrent UC sessions."""
#     async with modo_auth_lock:
#         try:
#             await authenticate_modo(driver, bot, None, channel)
#         except Exception as e:
#             print(f"[Modo Auth] error: {e}")

# async def modo_auth_maintenance():
#     """
#     Runs in the background, but only refreshes when:
#       - the main loop is NOT running, and
#       - the lock is free, and
#       - refresh is due.
#     This ensures manual !auth modo is responsive after !stop, and nothing collides.
#     """
#     await bot.wait_until_ready()
#     channel = bot.get_channel(DISCORD_CHANNEL)
#     while not bot.is_closed():
#         try:
#             if (not is_main_loop_running()
#                 and 'modo_auth_needs_refresh' in globals()
#                 and modo_auth_needs_refresh()
#                 and not modo_auth_lock.locked()):
#                 if channel:
#                     await channel.send(" Background: refreshing Modo auth…")
#                 await run_modo_auth(channel)
#         except Exception as e:
#             print(f"[Modo Auth Maintenance] outer error: {e}")
#         await asyncio.sleep(REFRESH_CHECK_MINUTES * 60)

# ───────────────────────────────────────────────────────────
# Commands
# ───────────────────────────────────────────────────────────
# ───────────────────────────────────────────────────────────
# Slash commands (/) and /profile
# ───────────────────────────────────────────────────────────
profile_group = app_commands.Group(name="profile", description="Set or view your Google and casino credentials")

@profile_group.command(name="set_google", description="Set your Google login (email and password) for universal casinos and Stake/Fortune Coins")
@app_commands.describe(email="Your Google email", password="Your Google password")
async def profile_set_google_slash(interaction: discord.Interaction, email: str, password: str):
    if not _slash_channel_check(interaction):
        await _slash_channel_fail(interaction)
        return
    if _profile_rate_limit_check(interaction.user.id):
        emb = embed_message("Rate limited", f"You can only run profile updates {PROFILE_RATE_LIMIT_PER_MINUTE} times per minute. Try again shortly.", EMBED_COLOR_WARN)
        await interaction.response.send_message(embed=emb, ephemeral=True)
        return
    email = (email or "").strip()
    password = (password or "").strip()
    if not email or not password:
        emb = embed_message("Missing input", "Please provide both email and password.", EMBED_COLOR_ERROR)
        await interaction.response.send_message(embed=emb, ephemeral=True)
        return
    user_profiles.set_google(interaction.user.id, email, password)
    emb = embed_message(
        "Google login saved",
        f"Credentials have been stored for **{interaction.user.display_name}**.",
        EMBED_COLOR_SUCCESS,
        fields=[{"name": "Email", "value": f"`{email}`", "inline": True}, {"name": "Password", "value": "••••••••", "inline": True}, {"name": "Tip", "value": "Use `/profile view` to confirm. Your password is stored securely.", "inline": False}],
    )
    await interaction.response.send_message(embed=emb, ephemeral=True)

@profile_group.command(name="set_casino", description="Set credentials for a specific casino (e.g. STAKE, CHANCED). Format: username:password")
@app_commands.describe(casino_name="Casino name (e.g. STAKE, CHANCED, FORTUNECOINS)", credentials="username:password")
async def profile_set_casino_slash(interaction: discord.Interaction, casino_name: str, credentials: str):
    if not _slash_channel_check(interaction):
        await _slash_channel_fail(interaction)
        return
    if _profile_rate_limit_check(interaction.user.id):
        emb = embed_message("Rate limited", f"You can only run profile updates {PROFILE_RATE_LIMIT_PER_MINUTE} times per minute. Try again shortly.", EMBED_COLOR_WARN)
        await interaction.response.send_message(embed=emb, ephemeral=True)
        return
    casino_name = (casino_name or "").strip()
    credentials = (credentials or "").strip()
    if not casino_name or not credentials:
        emb = embed_message("Missing input", "Please provide casino name and credentials (username:password).", EMBED_COLOR_ERROR)
        await interaction.response.send_message(embed=emb, ephemeral=True)
        return
    user_profiles.set_casino(interaction.user.id, casino_name, credentials)
    user = credentials.split(":", 1)[0] if ":" in credentials else "•••"
    emb = embed_message(
        "Casino credentials saved",
        f"**{casino_name}** has been linked to your profile.",
        EMBED_COLOR_SUCCESS,
        fields=[{"name": "Casino", "value": casino_name, "inline": True}, {"name": "Username", "value": f"`{user}`", "inline": True}, {"name": "User", "value": interaction.user.display_name, "inline": False}],
    )
    await interaction.response.send_message(embed=emb, ephemeral=True)

# Casino names users can pass to /profile set_casino (universal keys + known API casinos)
KNOWN_CASINO_NAMES_FOR_PROFILE: List[str] = sorted(
    set(k.upper() for k in UNIVERSAL_CASINO_KEYS)
    | {
        "STAKE", "CHANCED", "FORTUNECOINS", "MODO", "CROWNCOINS", "CHUMBA", "GLOBALPOKER",
        "JEFEBET", "SPINPALS", "SPINQUEST", "FUNRIZE", "REALPRIZE", "DINGDINGDING", "SPORTZINO",
        "NOLIMITCOINS", "SMILESCASINO", "JUMBO", "YAYCASINO", "LUCKYLAND", "LUCKYBIRD",
        "FORTUNEWHEELZ", "AMERICANLUCK", "ROLLINGRICHES",
    }
)

@profile_group.command(name="list_casinos", description="List casino names you can use with /profile set_casino")
async def profile_list_casinos_slash(interaction: discord.Interaction):
    names = ", ".join(f"`{n}`" for n in KNOWN_CASINO_NAMES_FOR_PROFILE[:50])
    if len(KNOWN_CASINO_NAMES_FOR_PROFILE) > 50:
        names += f" … and {len(KNOWN_CASINO_NAMES_FOR_PROFILE) - 50} more"
    emb = embed_message(
        "Casino names for /profile set_casino",
        "Use these (case-insensitive) with `/profile set_casino <name> username:password`.",
        EMBED_COLOR_INFO,
        fields=[{"name": "Names", "value": names or "*None*", "inline": False}],
    )
    await interaction.response.send_message(embed=emb, ephemeral=True)

@profile_group.command(name="view", description="View your saved profile (masks passwords)")
async def profile_view_slash(interaction: discord.Interaction):
    prof = user_profiles.get_profile(interaction.user.id)
    if not prof:
        emb = embed_message(
            "No profile yet",
            "You don't have any saved credentials. Add them to use universal casinos and casino-specific logins.",
            EMBED_COLOR_INFO,
            fields=[
                {"name": "Google login", "value": "`/profile set_google`", "inline": True},
                {"name": "Casino login", "value": "`/profile set_casino`", "inline": True},
            ],
        )
        await interaction.response.send_message(embed=emb, ephemeral=True)
        return
    google_val = "`" + prof["google_login"].split(":", 1)[0] + "` (password set)" if prof.get("google_login") else "*Not set*"
    casino_val = ", ".join(f"`{k}`" for k in (prof.get("casino") or {}).keys()) or "*None*"
    emb = embed_message(
        f"Profile — {interaction.user.display_name}",
        "Your saved credentials (passwords are never shown).",
        EMBED_COLOR_INFO,
        fields=[
            {"name": "Google", "value": google_val, "inline": True},
            {"name": "Casinos", "value": casino_val, "inline": True},
            {"name": "Manage", "value": "`/profile set_google` · `/profile set_casino` · `/profile clear`", "inline": False},
        ],
    )
    thumb = getattr(interaction.user, "display_avatar", None) or getattr(interaction.user, "avatar", None)
    if thumb:
        emb.set_thumbnail(url=thumb.url)
    await interaction.response.send_message(embed=emb, ephemeral=True)

@profile_group.command(name="clear", description="Clear your saved credentials")
@app_commands.describe(what="What to clear", casino_name="Casino name when clearing one casino (optional)")
@app_commands.choices(what=[
    app_commands.Choice(name="google", value="google"),
    app_commands.Choice(name="casino", value="casino"),
    app_commands.Choice(name="all", value="all"),
])
async def profile_clear_slash(interaction: discord.Interaction, what: app_commands.Choice[str], casino_name: str = None):
    w = what.value if hasattr(what, "value") else what
    if w == "google":
        ok = user_profiles.clear_google(interaction.user.id)
        title = "Google credentials cleared" if ok else "Nothing to clear"
        desc = "Your Google login has been removed from your profile." if ok else "You had no Google credentials saved."
        emb = embed_message(title, desc, EMBED_COLOR_SUCCESS if ok else EMBED_COLOR_WARN)
        await interaction.response.send_message(embed=emb, ephemeral=True)
    elif w == "casino":
        ok = user_profiles.clear_casino(interaction.user.id, casino_name)
        title = "Casino credentials cleared" if ok else "Not found"
        desc = (f"Cleared **{casino_name}**." if casino_name else "Cleared all casino credentials.") if ok else "No matching casino credentials found."
        emb = embed_message(title, desc, EMBED_COLOR_SUCCESS if ok else EMBED_COLOR_WARN)
        await interaction.response.send_message(embed=emb, ephemeral=True)
    else:  # all
        ok = user_profiles.clear_all(interaction.user.id)
        title = "Profile cleared" if ok else "Nothing to clear"
        desc = "All your saved credentials have been removed." if ok else "You had no profile saved."
        emb = embed_message(title, desc, EMBED_COLOR_SUCCESS if ok else EMBED_COLOR_WARN)
        await interaction.response.send_message(embed=emb, ephemeral=True)

bot.tree.add_command(profile_group)

def _slash_channel_check(interaction: discord.Interaction) -> bool:
    """Return True if command is allowed in this channel (for slash commands)."""
    if not DISCORD_CHANNEL:
        return True
    return interaction.channel_id == DISCORD_CHANNEL

async def _slash_channel_fail(interaction: discord.Interaction):
    emb = embed_message("Wrong channel", "Use this command in the configured casino channel.", EMBED_COLOR_WARN)
    await interaction.response.send_message(embed=emb, ephemeral=True)

@bot.tree.command(name="start", description="Start the automated casino claim loop")
async def start_slash(interaction: discord.Interaction):
    if not _slash_channel_check(interaction):
        await _slash_channel_fail(interaction)
        return
    started = await start_main_loop()
    if started:
        emb = embed_message("Loop started", "The automated casino claim loop is now running. Bonuses will be checked on schedule.", EMBED_COLOR_SUCCESS)
        await interaction.response.send_message(embed=emb)
    elif is_main_loop_running():
        emb = embed_message("Already running", "The casino loop is already active. Use `/stop` to stop it first.", EMBED_COLOR_WARN)
        await interaction.response.send_message(embed=emb)
    else:
        emb = embed_message("Could not start", "Channel missing or invalid. Check bot configuration.", EMBED_COLOR_ERROR)
        await interaction.response.send_message(embed=emb)

@bot.tree.command(name="stop", description="Stop the automated casino claim loop")
async def stop_slash(interaction: discord.Interaction):
    stopped = await stop_main_loop()
    if stopped:
        emb = embed_message("Loop stopped", "The automated loop has been stopped. You can run manual casino commands now.", EMBED_COLOR_SUCCESS)
        await interaction.response.send_message(embed=emb)
    else:
        emb = embed_message("Not running", "The casino loop was not running.", EMBED_COLOR_INFO)
        await interaction.response.send_message(embed=emb)

@bot.tree.command(name="help", description="List bot commands and usage")
async def help_slash(interaction: discord.Interaction):
    emb = embed_message(
        "Casino Claim — Help",
        "Never miss a casino bonus. Set your credentials with `/profile` and control the loop with `/start` and `/stop`.",
        EMBED_COLOR_INFO,
        fields=[
            {"name": "Slash commands", "value": "`/start` · `/stop` · `/profile` (set_google, set_casino, list_casinos, view, clear) · `/universal <key>` · `/status` · `/help`", "inline": False},
            {"name": "Prefix commands", "value": "`!start` · `!stop` · `!auth google` · `!universal <key>` · `!help` · and all casino commands (e.g. `!stake`)", "inline": False},
            {"name": "Getting started", "value": "1. `/profile set_google` — add your Google login\n2. `/profile set_casino` — add any casino (e.g. STAKE)\n3. `/start` — start the auto loop", "inline": False},
        ],
    )
    await interaction.response.send_message(embed=emb, ephemeral=True)

@bot.tree.command(name="universal", description="Check a universal (config-driven) casino by key")
@app_commands.describe(key="Casino key from casinos_universal.json (e.g. wowvegas, high5casino)")
async def universal_slash(interaction: discord.Interaction, key: str):
    if not _slash_channel_check(interaction):
        await _slash_channel_fail(interaction)
        return
    key = (key or "").lower().strip()
    if key not in UNIVERSAL_CASINO_KEYS:
        avail = ", ".join(UNIVERSAL_CASINO_KEYS) if UNIVERSAL_CASINO_KEYS else "none (add entries to casinos_universal.json)"
        emb = embed_message("Unknown key", f"Available keys: **{avail}**", EMBED_COLOR_WARN, fields=[{"name": "Example", "value": "`/universal wowvegas`", "inline": False}])
        await interaction.response.send_message(embed=emb, ephemeral=True)
        return
    try:
        from universal_casinoAPI import universal_casino_flow, load_universal_casinos_config
        configs = load_universal_casinos_config()
        cfg = next((c for c in configs if (c.get("key") or c.get("name", "").lower().replace(" ", "")) == key), None)
        if not cfg:
            emb = embed_message("Config not found", f"No config for key `{key}`.", EMBED_COLOR_ERROR)
            await interaction.response.send_message(embed=emb, ephemeral=True)
            return
        name = cfg.get("name", key)
        emb = embed_message(
            f"Checking {name}",
            "The bot is opening the site and will try to claim. Uses your `/profile` Google login if set.",
            EMBED_COLOR_INFO,
            fields=[{"name": "Casino", "value": name, "inline": True}, {"name": "Key", "value": key, "inline": True}],
        )
        await interaction.response.send_message(embed=emb)
        channel = bot.get_channel(DISCORD_CHANNEL)
        creds = user_profiles.get_google_credentials(interaction.user.id)
        if creds:
            cfg = dict(cfg)
            cfg["_user_google"] = creds
        await universal_casino_flow(driver, bot, channel, cfg, None)
    except Exception as e:
        err_emb = embed_message("Error", str(e)[:500], EMBED_COLOR_ERROR)
        try:
            await interaction.response.send_message(embed=err_emb, ephemeral=True)
        except discord.errors.InteractionResponded:
            await interaction.followup.send(embed=err_emb, ephemeral=True)
        except Exception:
            pass

@bot.tree.command(name="status", description="Show bot status: loop, next runs, universal casinos")
async def status_slash(interaction: discord.Interaction):
    if not _slash_channel_check(interaction):
        await _slash_channel_fail(interaction)
        return
    running = is_main_loop_running()
    now = dt.datetime.now(dt.timezone.utc)
    next_runs: List[str] = []
    for entry in casino_loop_entries[:15]:
        delta = (entry.next_run - now).total_seconds()
        if delta <= 0:
            next_runs.append(f"**{entry.display_name}**: due now")
        else:
            mins = int(delta // 60)
            next_runs.append(f"**{entry.display_name}**: in {mins}m")
    if len(casino_loop_entries) > 15:
        next_runs.append(f"… and {len(casino_loop_entries) - 15} more")
    emb = embed_message(
        "Casino Claim — Status",
        "Loop and schedule overview.",
        EMBED_COLOR_SUCCESS if running else EMBED_COLOR_INFO,
        fields=[
            {"name": "Loop", "value": "Running" if running else "Stopped", "inline": True},
            {"name": "Universal casinos", "value": str(len(UNIVERSAL_CASINO_KEYS)), "inline": True},
            {"name": "Next runs", "value": "\n".join(next_runs) if next_runs else "—", "inline": False},
        ],
    )
    await interaction.response.send_message(embed=emb, ephemeral=True)

@bot.event
async def on_ready():
    guild_id_str = (os.getenv("DISCORD_GUILD_ID") or "").strip()
    try:
        if guild_id_str:
            guild_id = int(guild_id_str)
            await bot.tree.sync(guild=discord.Object(id=guild_id))
            log.info("Slash commands synced to guild %s", guild_id)
        else:
            await bot.tree.sync()
            log.info("Slash commands synced (global).")
    except Exception as e:
        log.warning("Slash sync failed: %s", e)
    log.info("Bot connected as %s", bot.user)
    channel = bot.get_channel(DISCORD_CHANNEL)
    if channel:
        await channel.send(embed=embed_message("Bot started", "Discord bot has started. Loop will start shortly if configured.", EMBED_COLOR_SUCCESS))
        await asyncio.sleep(10)
        if await start_main_loop(channel):
            await channel.send(embed=embed_message("Loop started", "Casino loop started with current configuration.", EMBED_COLOR_SUCCESS))
    else:
        log.warning("DISCORD_CHANNEL invalid or channel not found.")

MANUAL_CASINO_COMMANDS = {
    "chumba","rollingriches","jefebet","spinpals","spinquest","funrize",
    "fortunewheelz","stake","chanced","luckybird","globalpoker","crowncoins",
    "dingdingding","modo","zula","sportzino","nolimitcoins","fortunecoins",
    "smilescasino","americanluck","yaycasino", "realprize", "jumbo",
    *UNIVERSAL_CASINO_KEYS,
}

@bot.check
async def prevent_manual_casino_commands(ctx: commands.Context) -> bool:
    if ctx.command is None:
        return True
    if is_main_loop_running() and ctx.command.name.lower() in MANUAL_CASINO_COMMANDS:
        await ctx.send(embed=embed_message("Loop running", "The automated casino loop is running. Use `!stop` or `/stop` before manually checking casinos.", EMBED_COLOR_WARN))
        return False
    return True

@bot.command(name="start")
async def start_loop_command(ctx: commands.Context):
    started = await start_main_loop()
    if started:
        await ctx.send(embed=embed_message("Loop started", "Casino loop started. Bonuses will be checked on schedule.", EMBED_COLOR_SUCCESS))
    elif is_main_loop_running():
        await ctx.send(embed=embed_message("Already running", "Casino loop is already running. Use `!stop` or `/stop` first.", EMBED_COLOR_WARN))
    else:
        await ctx.send(embed=embed_message("Could not start", "Casino loop could not start (channel missing). Check bot configuration.", EMBED_COLOR_ERROR))

@bot.command(name="stop")
async def stop_loop_command(ctx: commands.Context):
    stopped = await stop_main_loop()
    if stopped:
        await ctx.send(embed=embed_message("Loop stopped", "Casino loop stopped. You can run manual casino commands now.", EMBED_COLOR_SUCCESS))
    else:
        await ctx.send(embed=embed_message("Not running", "Casino loop is not currently running.", EMBED_COLOR_INFO))


@bot.command(name="cleardatadir")
async def clear_data_dir(ctx: commands.Context):
    global driver  # <-- must be before any use of driver in this function

    """
    Hot-clear the persistent Chrome user-data directory without killing the bot.
    Stops the loop, waits for any executor job to finish, quits Chrome,
    deletes the profile, recreates the driver, and (optionally) restarts the loop.
    """
    root = instance_dir or os.getenv("CHROME_USER_DATA_DIR", "").strip()
    if not root:
        await ctx.send(" No CHROME_INSTANCE_DIR or CHROME_USER_DATA_DIR configured — nothing to clear.")
        return
    ...
    # (everything else the same)


    await ctx.send(
        " **Clear Chrome data directory?**\n"
        f"This will stop the loop, quit Chrome, delete:\n```{root}```\n"
        "and then restart Chrome without restarting the bot.\n\n"
        "Type **YES** within 20 seconds to confirm, or anything else to cancel."
    )

    def _check(m: discord.Message) -> bool:
        return m.channel.id == ctx.channel.id and m.author.id == ctx.author.id

    try:
        reply: discord.Message = await bot.wait_for("message", timeout=20, check=_check)
    except asyncio.TimeoutError:
        await ctx.send(" Timed out — cancelled.")
        return

    if reply.content.strip().upper() != "YES":
        await ctx.send(" Cancelled.")
        return

    # 1) Stop automated loop
    await ctx.send(" Stopping the loop…")
    try:
        if is_main_loop_running():
            await stop_main_loop()
    except Exception:
        pass

    # 2) Wait briefly for any background executor job (e.g., FC) to finish
    await ctx.send(" Waiting for background tasks to finish (up to 20s)…")
    for _ in range(40):  # 40 * 0.5s = 20s
        with _active_exec_lock:
            busy = _active_exec_jobs
        if busy == 0:
            break
        await asyncio.sleep(0.5)
    else:
        await ctx.send(" Background task still running; proceeding anyway.")

    # 3) Quit Chrome to release locks
    await ctx.send(" Quitting Chrome…")
    try:
        driver.quit()
    except Exception:
        pass

    # 4) Kill any stray Chrome
    try:
        import psutil, signal
        killed = 0
        for p in psutil.process_iter(attrs=["name", "cmdline"]):
            nm = (p.info.get("name") or "").lower()
            cmd = " ".join(p.info.get("cmdline") or [])
            if "chrome" in nm or "chromium" in nm:
                if (not root) or (f"--user-data-dir={root}" in cmd):
                    try:
                        p.send_signal(signal.SIGKILL); killed += 1
                    except Exception:
                        pass
        if killed:
            await ctx.send(f" Killed {killed} stray Chrome processes.")
    except Exception:
        pass

    # 5) Delete the profile directory
    await ctx.send(f" Clearing Chrome user-data at:\n```{root}```")
    try:
        import shutil
        shutil.rmtree(root, ignore_errors=True)
        await ctx.send(" Chrome user-data cleared.")
    except Exception as e:
        await ctx.send(f" Failed to clear profile dir: `{e}`")
        return

    # 6) Recreate the WebDriver (fresh profile)
    await ctx.send(" Restarting Chrome with a fresh profile…")
    try:
        # (re)apply any flags in case code refactors later
        _apply_common_chrome_flags(options)
        driver = _build_driver_with_retry(options)
        await ctx.send(" Chrome restarted.")
    except Exception as e:
        await ctx.send(f" Failed to restart Chrome: `{e}`")
        return

    # 7) (Optional) Restart the loop automatically
    try:
        channel = bot.get_channel(DISCORD_CHANNEL)
        if channel and not is_main_loop_running():
            await start_main_loop(channel)
            await ctx.send(" Casino loop restarted.")
    except Exception:
        pass



# ───────────────────────────────────────────────────────────
# !reset — clear profile, rebuild, and re-compose (supports "nocache")
# Usage:
#   !reset           -> docker compose build
#   !reset nocache   -> docker compose build --no-cache
# ───────────────────────────────────────────────────────────
import os
import shutil
import asyncio
import subprocess
from asyncio.subprocess import PIPE
from typing import List, Optional

try:
    import psutil  # optional; used to kill straggler chrome
except Exception:
    psutil = None

try:
    import signal
except Exception:
    signal = None

# If your code defines these, we'll call them. Otherwise we noop.
def _has_callable(name: str) -> bool:
    return name in globals() and callable(globals()[name])

def _maybe_is_main_loop_running() -> bool:
    try:
        if _has_callable("is_main_loop_running"):
            return bool(globals()["is_main_loop_running"]())
    except Exception:
        pass
    return False

async def _maybe_stop_main_loop() -> None:
    try:
        if _has_callable("stop_main_loop"):
            await globals()["stop_main_loop"]()
    except Exception:
        pass

def _maybe_quit_driver() -> None:
    # Works if you keep a global `driver`/`sb` around; otherwise it’s a no-op.
    for key in ("driver", "sb", "browser", "web_driver"):
        if key in globals():
            try:
                obj = globals()[key]
                if obj:
                    # selenium webdriver has .quit(); SeleniumBase SB has .quit()
                    getattr(obj, "quit", lambda: None)()
            except Exception:
                pass

def _docker_compose_cmd() -> List[str]:
    """
    Prefer modern 'docker compose', fallback to legacy 'docker-compose'.
    Returns [] if neither is available in PATH.
    """
    if shutil.which("docker"):
        try:
            out = subprocess.run(
                ["docker", "compose", "version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5,
            )
            if out.returncode == 0:
                return ["docker", "compose"]
        except Exception:
            pass
    if shutil.which("docker-compose"):
        return ["docker-compose"]
    return []

async def _stream_proc_to_discord(ctx, proc: asyncio.subprocess.Process, prefix: str) -> int:
    """
    Stream a running process's stdout/stderr to Discord in safe 1.8k chunks.
    """
    buf = ""

    async def flush():
        nonlocal buf
        if not buf:
            return
        chunks = [buf[i:i+1800] for i in range(0, len(buf), 1800)]
        for c in chunks:
            try:
                await ctx.send(f"{prefix}```\n{c}\n```")
            except Exception:
                pass
        buf = ""

    if proc.stdout:
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            buf += line.decode(errors="ignore")
            if len(buf) >= 1600:
                await flush()
    await flush()
    await proc.wait()

    if proc.returncode != 0 and proc.stderr:
        err = (await proc.stderr.read()).decode(errors="ignore")
        if err.strip():
            for i in range(0, len(err), 1800):
                try:
                    await ctx.send(f"{prefix}(stderr)```\n{err[i:i+1800]}\n```")
                except Exception:
                    pass

    return proc.returncode

def _detect_user_data_dir() -> Optional[str]:
    """
    Tries a few common envs/variables you've used across modules.
    """
    # If your code sets `instance_dir` globally, prefer it.
    if "instance_dir" in globals():
        val = str(globals()["instance_dir"]) or ""
        if val.strip():
            return val.strip()

    # Common envs you've used in past conversations:
    for env_key in ("CHROME_INSTANCE_DIR", "CHROME_USER_DATA_DIR", "SB_USER_DATA_DIR"):
        val = os.getenv(env_key, "").strip()
        if val:
            return val
    return None

# ───────────────────────────────────────────────────────────
# !reset — helper-container handoff with reliable fallback
#   !reset           -> build cached; recreate TARGET_SERVICE only
#   !reset nocache   -> build --no-cache; recreate TARGET_SERVICE only
# Keeps watchtower running the whole time.
# ───────────────────────────────────────────────────────────
import os
import asyncio
import shutil
import subprocess
from asyncio.subprocess import PIPE
from typing import Optional

try:
    import psutil, signal
except Exception:
    psutil = None
    signal = None

def _has_callable(name: str) -> bool:
    return name in globals() and callable(globals()[name])

def _maybe_is_main_loop_running() -> bool:
    try:
        if _has_callable("is_main_loop_running"):
            return bool(globals()["is_main_loop_running"]())
    except Exception:
        pass
    return False

async def _maybe_stop_main_loop() -> None:
    try:
        if _has_callable("stop_main_loop"):
            await globals()["stop_main_loop"]()
    except Exception:
        pass

def _maybe_quit_driver() -> None:
    for key in ("driver", "sb", "browser", "web_driver"):
        if key in globals():
            try:
                obj = globals()[key]
                if obj:
                    getattr(obj, "quit", lambda: None)()
            except Exception:
                pass

def _detect_user_data_dir() -> Optional[str]:
    if "instance_dir" in globals():
        v = str(globals()["instance_dir"]) or ""
        if v.strip():
            return v.strip()
    for k in ("CHROME_INSTANCE_DIR", "CHROME_USER_DATA_DIR", "SB_USER_DATA_DIR"):
        v = os.getenv(k, "").strip()
        if v:
            return v
    return None

def _q(s: str) -> str:
    return "'" + s.replace("'", "'\"'\"'") + "'"

async def _run(ctx, args, cwd=None, prefix=""):
    """Run a short command and stream a little output to Discord."""
    proc = await asyncio.create_subprocess_exec(*args, cwd=cwd, stdout=PIPE, stderr=PIPE)
    out = (await proc.stdout.read()).decode(errors="ignore")
    err = (await proc.stderr.read()).decode(errors="ignore")
    rc = await proc.wait()
    if out.strip():
        await ctx.send(f"{prefix}```\n{out[-1700:]}\n```")
    if rc != 0 and err.strip():
        await ctx.send(f"{prefix}(stderr)```\n{err[-1700:]}\n```")
    return rc, out, err

@bot.command(name="reset")
async def reset_cmd(ctx, mode: str = ""):
    compose_dir   = os.getenv("COMPOSE_DIR", os.getcwd()).strip()
    compose_file  = os.getenv("COMPOSE_FILE", "").strip() or os.path.join(compose_dir, "docker-compose.yml")
    helper_image  = os.getenv("RESET_HELPER_IMAGE", "g8tsz/sweepstakes-autoclaim:testing").strip()
    project_name  = os.getenv("COMPOSE_PROJECT_NAME", "").strip()     # optional
    target_svc    = os.getenv("TARGET_SERVICE", "casino-bot").strip()
    nocache       = "nocache" in (mode or "").lower()
    user_data     = _detect_user_data_dir()

    # sanity
    if not shutil.which("docker"):
        await ctx.send(" Docker CLI not found in PATH. Install docker-cli in this container.")
        return
    if not os.path.exists(compose_file):
        await ctx.send(f" Compose file not found at `{compose_file}`.")
        return

    await ctx.send(
        " **Reset requested**\n"
        f"• Compose dir: `{compose_dir}`\n"
        f"• Compose file: `{compose_file}`\n"
        f"• Target service: `{target_svc}` (watchtower stays running)\n"
        f"• Chrome profile: `{user_data or '(none configured)'}`\n"
        f"• Build mode: `{'--no-cache' if nocache else '(cached)'}`\n"
        f"• Helper image: `{helper_image}`\n\n"
        "Type **YES** within 20 seconds to proceed. Anything else cancels."
    )

    def _check(m: discord.Message) -> bool:
        return m.channel.id == ctx.channel.id and m.author.id == ctx.author.id

    try:
        reply: discord.Message = await bot.wait_for("message", timeout=20, check=_check)
    except asyncio.TimeoutError:
        await ctx.send(" Timed out — cancelled.")
        return
    if reply.content.strip().upper() != "YES":
        await ctx.send(" Cancelled.")
        return

    # 1) Stop loop & close browser
    await ctx.send(" Stopping loop & shutting down Chrome…")
    try:
        if _maybe_is_main_loop_running():
            await _maybe_stop_main_loop()
    except Exception:
        pass
    _maybe_quit_driver()

    # 2) Kill stray Chrome using same profile
    if psutil and signal:
        try:
            killed = 0
            for p in psutil.process_iter(attrs=["name","cmdline"]):
                nm = (p.info.get("name") or "").lower()
                cmd = " ".join(p.info.get("cmdline") or [])
                if "chrome" in nm or "chromium" in nm:
                    if (not user_data) or (f"--user-data-dir={user_data}" in cmd):
                        try:
                            p.send_signal(signal.SIGKILL); killed += 1
                        except Exception:
                            pass
            if killed:
                await ctx.send(f" Killed {killed} stray Chrome processes.")
        except Exception:
            pass

    # 3) Clear profile
    if user_data:
        await ctx.send(f" Clearing Chrome user-data at:\n```{user_data}```")
        try:
            shutil.rmtree(user_data, ignore_errors=True)
            await ctx.send(" Chrome user-data cleared.")
        except Exception as e:
            await ctx.send(f" Failed to clear profile dir: `{e}` (continuing)")

    # 4) Try helper container first (best path)
    await ctx.send(" Launching reset helper (rebuild & recreate target service only)…")

    pn = f" --project-name {_q(project_name)}" if project_name else ""
    cf = f" -f {_q(compose_file)}"
    nc = " --no-cache" if nocache else ""

    helper_name = "casino-reset-helper"
    helper_script = (
        "set -euo pipefail; "
        f"docker rm -f {_q(target_svc)} || true; "
        # pull to ensure the helper image (if using same) has latest compose plugin/clis
        f"docker compose{pn}{cf} build{nc} {_q(target_svc)}; "
        f"docker compose{pn}{cf} up -d --no-deps --remove-orphans {_q(target_svc)}"
    )

    # Pull helper image (nice to have)
    await _run(ctx, ["docker", "pull", helper_image], prefix="pull ")

    run_cmd = [
        "docker","run","-d","--rm",
        "--name", helper_name,
        "-v","/var/run/docker.sock:/var/run/docker.sock",
        "-v", f"{compose_dir}:{compose_dir}",
        "-w", compose_dir,
        helper_image,
        "sh","-lc", helper_script
    ]
    rc, out, err = await _run(ctx, run_cmd, prefix="run ")

    if rc == 0 and out.strip():
        helper_id = out.strip()[:12]
        await ctx.send(
            f" Helper started as `{helper_id}`.\n"
            f"It will rebuild & up **{target_svc}** only. Watchtower stays running.\n"
            f"To watch progress from host: `docker logs -f {helper_name}`"
        )
        await ctx.send(" Exiting current bot container so the helper can replace it.")
        try:
            await bot.close()
        finally:
            os._exit(0)
        return

    # 5) Fallback: background a host-side nohup reset (no helper container)
    await ctx.send(" Helper failed to start. Falling back to host-side background reset…")
    bg_log = "/tmp/reset-fallback.log"
    script = (
        f"set -euo pipefail; "
        f"docker rm -f { _q(target_svc) } || true; "
        f"docker compose{pn}{cf} build{nc} { _q(target_svc) }; "
        f"docker compose{pn}{cf} up -d --no-deps --remove-orphans { _q(target_svc) }"
    )
    # Spawn in background so this container can exit
    bg_cmd = ["sh","-lc", f"nohup sh -lc { _q(script) } > {bg_log} 2>&1 & echo $!"]
    rc2, out2, err2 = await _run(ctx, bg_cmd, cwd=compose_dir, prefix="fallback ")

    if rc2 == 0:
        pid = out2.strip()
        await ctx.send(
            f" Background reset launched (PID {pid}).\n"
            f"Logs: `{bg_log}` inside this container (until it exits). "
            "From the host you can also run:\n"
            f"```bash\ndocker compose -f {compose_file} ps\n"
            f"docker logs -f {target_svc}\n```"
        )
        await ctx.send(" Exiting current bot container now.")
        try:
            await bot.close()
        finally:
            os._exit(0)
        return

    # 6) If we got here, both helper and fallback failed; keep the bot alive and show errors
    await ctx.send(" Reset helper and fallback both failed. Check the stderr above and your Docker setup.")



def format_loop_config() -> str:
    status = "running" if is_main_loop_running() else "stopped"
    lines = [" **Casino loop configuration**", f"Status: **{status}**", "Order and intervals:"]
    for i, e in enumerate(casino_loop_entries, 1):
        lines.append(f"{i}. {e.display_name} (`{e.key}`) – every {e.interval_minutes:.1f} minutes")
    lines += ["", "Use `!config interval <casino> <minutes>` to change an interval.",
              "Use `!config order <casino1> <casino2> ...>` to set a new run order."]
    return "\n".join(lines)

from discord.ext import commands as dcommands
@dcommands.group(name="config", invoke_without_command=True)
async def _config(ctx: dcommands.Context):
    await ctx.send(format_loop_config())
bot.add_command(_config)

@_config.command(name="interval")
async def config_interval(ctx: dcommands.Context, casino: str, minutes: float):
    target = next((e for e in casino_loop_entries if e.key.lower() == casino.lower()), None)
    if not target:
        await ctx.send(f"Casino `{casino}` is not part of the automated loop.")
        return
    if minutes <= 0:
        await ctx.send("Interval must be greater than zero.")
        return
    target.interval_minutes = minutes
    target.next_run = dt.datetime.now(dt.timezone.utc)
    await ctx.send(f"Updated {target.display_name} to run every {minutes:.1f} minutes.")

@_config.command(name="order")
async def config_order(ctx: dcommands.Context, *casinos: str):
    if not casinos:
        await ctx.send("Provide the complete list of casino keys in the desired order.")
        return
    desired = [c.lower() for c in casinos]
    current = [e.key for e in casino_loop_entries]
    if len(desired) != len(current) or set(desired) != set(current):
        await ctx.send(f"You must include each of: {', '.join(current)} (exactly once).")
        return
    lookup = {e.key: e for e in casino_loop_entries}
    casino_loop_entries[:] = [lookup[k] for k in desired]
    reset_loop_schedule()
    await ctx.send("Casino loop order updated.\n" + format_loop_config())

@bot.command(name="ping")
async def ping(ctx): await ctx.send("Pong")

@bot.command(name="about")
async def about(ctx):
    await ctx.send(" Retrieving Chrome version …")
    driver.get("chrome://version/")
    await asyncio.sleep(2)
    try:
        version_raw = driver.find_element(By.ID, "version").text
        version_num = version_raw.split()[0]
    except Exception:
        version_num = "unknown "
    snap = "chrome_version.png"
    driver.save_screenshot(snap)
    await ctx.send(f" **Chrome build:** `{version_num}`", file=discord.File(snap))
    os.remove(snap)

@bot.command(name="restart")
async def restart(ctx):
    await ctx.send("Restarting…")
    await bot.close()
    os._exit(0)

# Manual casino commands
@bot.command(name="luckybird", aliases=["lb", "lucky bird"])
async def luckybird_cmd(ctx):
    await ctx.send("Checking LuckyBird for bonus…")
    channel = bot.get_channel(DISCORD_CHANNEL)
    await luckybird_entry(ctx, driver, bot, channel)


# manual command
@bot.command(name="realprize", aliases=["real prize", "rp"])
async def realprize_cmd(ctx):
    await ctx.send("Checking RealPrize for bonus…")
    await realprize_uc(ctx, bot.get_channel(DISCORD_CHANNEL))

@bot.command(name="zula", aliases=["zula casino", "zulacasino"])
async def zula_cmd(ctx):
    await ctx.send("Checking Zula Casino for bonus…")
    channel = bot.get_channel(DISCORD_CHANNEL)
    await zula_uc(ctx, channel)

@bot.command(name="sportzino")
async def sportzino_cmd(ctx):
    await ctx.send("Checking Sportzino for bonus…")
    await Sportzino(ctx, driver, bot.get_channel(DISCORD_CHANNEL))

@bot.command(name="nolimitcoins", aliases=["nlc", "no limit", "no limit coins"])
async def nolimitcoins_cmd(ctx):
    await ctx.send("Checking NoLimitCoins for bonus…")
    await nolimitcoins_flow(ctx, driver, bot.get_channel(DISCORD_CHANNEL))

@bot.command(name="funrize")
async def funrize_cmd(ctx):
    await ctx.send("Checking Funrize for bonus…")
    await funrize_flow(ctx, driver, bot.get_channel(DISCORD_CHANNEL))


@bot.command(name="yaycasino", aliases=["yay", "yay casino"])
async def yaycasino_cmd(ctx):
    await ctx.send("Checking YayCasino for bonus…")
    channel = bot.get_channel(DISCORD_CHANNEL)
    await yaycasino_uc(ctx, channel)


@bot.command(name="globalpoker", aliases=["gp", "global poker"])
async def globalpoker_cmd(ctx):
    await ctx.send("Checking GlobalPoker for bonus…")
    await global_poker(ctx, driver, bot.get_channel(DISCORD_CHANNEL))

@bot.command(name="jefebet", aliases=["jefe", "jefebet casino", "jefe bet", "jb"])
async def jefebet_cmd(ctx):
    await ctx.send("Checking JefeBet for bonus…")
    await jefebet_casino(ctx, driver, bot.get_channel(DISCORD_CHANNEL))

@bot.command(name="smilescasino", aliases=["smiles", "smiles casino"])
async def smilescasino_cmd(ctx):
    await ctx.send("Checking Smiles Casino for bonus...")
    await smilescasino_casino(ctx, driver, bot.get_channel(DISCORD_CHANNEL))

@bot.command(name="jumbo")
async def jumbo_cmd(ctx):
    await ctx.send("Checking Jumbo for bonus...")
    await jumbo_casino(ctx, driver, bot.get_channel(DISCORD_CHANNEL))

@bot.command(name="crowncoins")
async def crowncoins_cmd(ctx):
    await ctx.send("Checking Crown Coins Casino for bonus…")
    await crowncoins_casino(driver, bot, ctx, bot.get_channel(DISCORD_CHANNEL))

@bot.command(name="americanluck", aliases=["aluck", "a-luck", "american luck"])
async def americanluck_cmd(ctx):
    await ctx.send("Checking American Luck for bonus…")
    channel = bot.get_channel(DISCORD_CHANNEL)
    await americanluck_uc(ctx, channel)


@bot.command(name="modo")
async def modo_cmd(ctx):
    await ctx.send("Checking Modo for bonus…")
    channel = bot.get_channel(DISCORD_CHANNEL)
    ok = await claim_modo_bonus(driver, bot, ctx, channel)
    if not ok:
        await check_modo_countdown(driver, bot, ctx, channel)

@bot.command(name="rollingriches", aliases=["rr", "rolling riches"])
async def rollingriches_cmd(ctx):
    await ctx.send("Checking Rolling Riches for bonus…")
    channel = bot.get_channel(DISCORD_CHANNEL)
    await rolling_riches_casino(ctx, driver, channel)

@bot.command(name="luckyland", aliases=["lucky land"])
async def luckyland_cmd(ctx):
    await ctx.send("Checking LuckyLand for bonus…")
    channel = bot.get_channel(DISCORD_CHANNEL)
    await luckyland_uc(ctx, channel)



@bot.command(name="stake")
async def stake_cmd(ctx):
    await ctx.send("Checking Stake for bonus…")
    await stake_claim(driver, bot, ctx, bot.get_channel(DISCORD_CHANNEL))

@bot.command(name="fortunewheelz")
async def fortunewheelz_cmd(ctx):
    await ctx.send("Checking Fortune Wheelz for bonus…")
    await fortunewheelz_flow(ctx, driver, bot.get_channel(DISCORD_CHANNEL))

@bot.command(name="fortunecoins", aliases=["fortune coins", "fc"])
async def fortunecoins_cmd(ctx):
    await ctx.send("Checking Fortune Coins for bonus…")
    channel = bot.get_channel(DISCORD_CHANNEL)
    loop = asyncio.get_running_loop()
    from fortunecoinsAPI import fortunecoins_uc_blocking
    _exec_job_started()
    try:
        await loop.run_in_executor(_executor, fortunecoins_uc_blocking, bot, channel.id, loop)
    finally:
        _exec_job_finished()

@bot.command(name="spinquest")
async def spinquest_cmd(ctx):
    await ctx.send("Checking SpinQuest for bonus…")
    await spinquest_flow(ctx, driver, bot.get_channel(DISCORD_CHANNEL))

@bot.command(name="spinpals")
async def spinpals_cmd(ctx):
    await ctx.send("Checking SpinPals for bonus…")
    await spinpals_flow(ctx, driver, bot.get_channel(DISCORD_CHANNEL))

@bot.command(name="chumba")
async def chumba_cmd(ctx):
    await ctx.send("Checking Chumba for bonus…")
    driver.get("https://lobby.chumbacasino.com/")
    await asyncio.sleep(5)
    if driver.current_url.startswith("https://login.chumbacasino.com/"):
        authenticated = await authenticate_chumba(driver, bot, ctx)
        if not authenticated:
            await ctx.send("Chumba authentication failed.")
            return
    if driver.current_url.startswith("https://lobby.chumbacasino.com/"):
        await claim_chumba_bonus(driver, ctx)
        await check_chumba_countdown(driver, ctx)
    else:
        await ctx.send("Failed to reach the Chumba lobby.")

@bot.command(name="chanced")
async def chanced_cmd(ctx):
    await ctx.send("Checking Chanced.com for bonus…")
    creds = os.getenv("CHANCED")
    if creds:
        u, p = creds.split(":", 1)
        pair = (u, p)
    else:
        pair = (None, None)
    await chanced_casino(ctx, driver, bot.get_channel(DISCORD_CHANNEL), pair)

@bot.command(name="dingdingding")
async def dingdingding_cmd(ctx):
    await ctx.send("Checking DingDingDing for bonus…")
    channel = bot.get_channel(DISCORD_CHANNEL)
    claimed = await claim_dingdingding_bonus(driver, bot, ctx, channel)
    if not claimed:
        await check_dingdingding_countdown(driver, bot, ctx, channel)


@bot.command(name="universal", aliases=["u"])
async def universal_casino_cmd(ctx: commands.Context, key: str = None):
    """Run a universal (config-driven) casino by key. Keys from casinos_universal.json."""
    if not key:
        if UNIVERSAL_CASINO_KEYS:
            await ctx.send(f"Usage: `!universal <key>` — keys: {', '.join(UNIVERSAL_CASINO_KEYS)}")
        else:
            await ctx.send("No universal casinos loaded. Add entries to casinos_universal.json.")
        return
    key = key.lower().strip()
    if key not in UNIVERSAL_CASINO_KEYS:
        await ctx.send(f"Unknown universal casino `{key}`. Keys: {', '.join(UNIVERSAL_CASINO_KEYS)}")
        return
    try:
        from universal_casinoAPI import universal_casino_flow, load_universal_casinos_config
        configs = load_universal_casinos_config()
        cfg = next((c for c in configs if (c.get("key") or c.get("name", "").lower().replace(" ", "")) == key), None)
        if not cfg:
            await ctx.send(f"Config for `{key}` not found.")
            return
        await ctx.send(f"Checking {cfg.get('name', key)}…")
        channel = bot.get_channel(DISCORD_CHANNEL)
        await universal_casino_flow(driver, bot, channel, cfg, ctx)
    except Exception as e:
        await ctx.send(f"Error: {e}")


# ───────────────────────────────────────────────────────────
# AUTH ROUTER (restores !auth commands, including !auth modo)
# ───────────────────────────────────────────────────────────
@bot.command(name="auth")
async def authenticate_command(ctx: commands.Context, site: str, method: str = None):
    """
    Examples:
      !auth google
      !auth modo
      !auth nolimitcoins google
      !auth crowncoins env
    """
    channel = bot.get_channel(DISCORD_CHANNEL)
    norm_site = re.sub(r"\s+", "", site.lower())

    # 1) Global Google: !auth google
    if norm_site == "google":
        await ctx.send("Authenticating Google Account…")
        google_credentials = os.getenv("GOOGLE_LOGIN")
        if google_credentials:
            u, p = google_credentials.split(":", 1)
            creds = (u, p)
        else:
            await ctx.send(" Google credentials not found in `.env` (`GOOGLE_LOGIN`).")
            creds = (None, None)
        try:
            await google_auth(ctx, driver, channel, creds)
        except Exception as e:
            snap = "google_auth_failed.png"
            try:
                driver.save_screenshot(snap)
                await ctx.send(f"Google auth error: `{e}`", file=discord.File(snap))
            finally:
                try: os.remove(snap)
                except Exception: pass
        return

    # 2) Modo
    if norm_site == "modo":
        await ctx.send("Authenticating Modo…")
        await run_modo_auth(channel)  # serialized + safe against background task
        return

    # 3) CrownCoins
    if norm_site == "crowncoins":
        if method is None:
            await ctx.send("Usage: `!auth crowncoins google` or `!auth crowncoins env`")
            return
        if method.lower() == "google":
            await ctx.send("Authenticating CrownCoins via Google…")
            ok = await auth_crown_google(driver, bot, ctx, channel)
        elif method.lower() == "env":
            await ctx.send("Authenticating CrownCoins via .env credentials…")
            ok = await auth_crown_env(driver, bot, ctx, channel)
        else:
            await ctx.send("Invalid method. Use `google` or `env`.")
            return
        if not ok:
            snap = f"crowncoins_{method.lower()}_auth_failed.png"
            try:
                driver.save_screenshot(snap)
                await ctx.send("CrownCoins authentication failed.", file=discord.File(snap))
            finally:
                try: os.remove(snap)
                except Exception: pass
        return

    # 4) DingDingDing
    if norm_site == "dingdingding":
        await ctx.send("Authenticating DingDingDing…")
        ok = await authenticate_dingdingding(driver, bot, ctx, channel)
        if not ok:
            snap = "dingdingding_auth_failed.png"
            try:
                driver.save_screenshot(snap)
                await ctx.send("Authentication failed.", file=discord.File(snap))
            finally:
                try: os.remove(snap)
                except Exception: pass
        return

    # 5) Stake
    if norm_site == "stake":
        await ctx.send("Authenticating Stake…")
        ok = await stake_auth(driver, bot, ctx, channel)
        if not ok:
            snap = "stake_auth_failed.png"
            try:
                driver.save_screenshot(snap)
                await ctx.send("Stake authentication failed.", file=discord.File(snap))
            finally:
                try: os.remove(snap)
                except Exception: pass
        return

    # 6) LuckyBird
    if norm_site == "luckybird":
        await ctx.send("Authenticating LuckyBird…")
        ok = await authenticate_luckybird(driver, bot, ctx, channel)
        if not ok:
            snap = "luckybird_auth_failed.png"
            try:
                driver.save_screenshot(snap)
                await ctx.send("LuckyBird authentication failed.", file=discord.File(snap))
            finally:
                try: os.remove(snap)
                except Exception: pass
        return

    # 7) NoLimitCoins
    if norm_site in {"nolimitcoins", "nlc", "nolimit", "nolimitcoins", "no limit coins"}:
        if method is None:
            await ctx.send("Usage: `!auth nolimitcoins google` or `!auth nolimitcoins env`")
            return
        if method.lower() == "google":
            await ctx.send("Authenticating NoLimitCoins via Google…")
            ok = await auth_nolimit_google(driver, channel, ctx)
        elif method.lower() == "env":
            await ctx.send("Authenticating NoLimitCoins via .env credentials…")
            ok = await auth_nolimit_env(driver, channel, ctx)
        else:
            await ctx.send("Invalid method. Use `google` or `env`.")
            return

        if not ok:
            snap = f"nolimit_{method.lower()}_auth_failed.png"
            try:
                driver.save_screenshot(snap)
                await ctx.send("NoLimitCoins authentication failed.", file=discord.File(snap))
            finally:
                try: os.remove(snap)
                except Exception: pass
        return

    await ctx.send(f" Authentication for `{site}` is not implemented. Run `!help` for supported sites.")

# Handy shortcut specifically for Modo
@bot.command(name="authmodo")
async def authmodo_cmd(ctx):
    await ctx.send("Authenticating Modo…")
    await run_modo_auth(bot.get_channel(DISCORD_CHANNEL))

# ───────────────────────────────────────────────────────────
# Invalid command handler
# ───────────────────────────────────────────────────────────
@bot.event
async def on_command_error(ctx: commands.Context, error: Exception):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send(" Invalid command. Run `!help` to see valid commands.")
        return
    if isinstance(error, commands.BadArgument):
        await ctx.send(f" {error}")
        return
    try:
        log.exception("on_command_error: %s: %s", type(error).__name__, error)
    except Exception:
        pass
    await ctx.send(" An error occurred while handling that command.")

# ───────────────────────────────────────────────────────────
# Help Command
# ───────────────────────────────────────────────────────────
@bot.command(name="help")
async def help_cmd(ctx):
    emb = embed_message(
        "Casino Claim — Help",
        "Never miss a casino bonus. Set credentials with `/profile` and control the loop with `/start` and `/stop`.",
        EMBED_COLOR_INFO,
        fields=[
            {"name": "Slash commands", "value": "`/start` · `/stop` · `/profile` (set_google, set_casino, list_casinos, view, clear) · `/universal <key>` · `/status` · `/help`", "inline": False},
            {"name": "Prefix commands", "value": "`!start` · `!stop` · `!auth google` · `!universal <key>` · `!help` · and casino commands (e.g. `!stake`, `!chanced`)", "inline": False},
            {"name": "Getting started", "value": "1. `/profile set_google` — add your Google login\n2. `/profile set_casino` — add a casino (use `/profile list_casinos` for names)\n3. `/start` — start the auto loop", "inline": False},
        ],
    )
    await ctx.send(embed=emb)

# ───────────────────────────────────────────────────────────
# Run bot
# ───────────────────────────────────────────────────────────
bot.run(DISCORD_TOKEN)
