# Casino Claim 
Never miss a casino bonus again. A **full HTML website** with automation for claiming social casino bonuses—login, set your credentials, start the loop or run a casino now, and submit 2FA in the browser.

<p>
<img src="https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54"/>
<img src="https://img.shields.io/badge/-selenium-%43B02A?style=for-the-badge&logo=selenium&logoColor=white"/>
<img src="https://img.shields.io/badge/-FastAPI-%232c2f33?style=for-the-badge&logo=fastapi&logoColor=white"/>
<img src="https://img.shields.io/badge/-discord.py-%232c2f33?style=for-the-badge&logo=discord&logoColor=white"/>
<img src="https://img.shields.io/badge/-docker-%232c2f33?style=for-the-badge&logo=docker&logoColor=white"/>

</p>

# About 
Casino Claim is a **website + automation** app: you use the browser to sign up, store your Google and casino credentials, turn the automated loop on or off, run a single casino claim now, and enter 2FA when prompted. The same automation is also available as an optional Discord bot.

# DISCLAIMER 
I am not responsible for any financial loss or gain incurred with the use of this tool. I have no relationship with any business or website. This tool is for educational purposes only and is provided as is with no warranty.

# Security
- **Credentials**: `.env` and `user_profiles.json` contain sensitive data (tokens, passwords). Restrict file permissions (e.g. `chmod 600`), do not commit them to version control, and avoid sharing or backing them up to untrusted locations.
- **Discord**: Use a dedicated private channel for the bot (`DISCORD_CHANNEL`) so only intended users can trigger claims and see output.
- **Optional encryption**: Set `PROFILE_ENCRYPTION_KEY` to a Fernet key (from `cryptography.fernet.Fernet.generate_key()`) to encrypt `user_profiles.json` on disk. Requires the `cryptography` package.
- **Audit**: Set `PROFILE_AUDIT_LOG` to a file path to log profile actions (user id + action, no credentials).

# Having an Issue? 
For direct support, feature/casino requests, and community access, please sponsor me below and I will help you on Discord (exclusive to Sponsors and Contributors only).

[![Sponsor](https://img.shields.io/badge/sponsor-30363D?style=for-the-badge&logo=GitHub-Sponsors&logoColor=white)](https://github.com/sponsors/g8tsz)

# Acknowledgement 
This program is heavily inspired by auto-rsa from Nelson Dane. Go check it out and give it a star here: https://github.com/NelsonDane/auto-rsa


# Quick start (website)

```bash
git clone https://github.com/g8tsz/sweepstakes-autoclaim-.git
cd sweepstakes-autoclaim-
pip install -r requirements.txt
python run_web.py
```

Open **http://localhost:8000** — sign up, then use **Profile** to set your Google and casino credentials, **Dashboard** to start the loop or run a casino now, and **History** to see results. When a run needs 2FA, the dashboard shows a form to enter the code.

# Installation (website)

1. **Python 3.9+** and pip.
2. Clone the repo and install dependencies:
   ```bash
   git clone https://github.com/g8tsz/sweepstakes-autoclaim-.git
   cd sweepstakes-autoclaim-
   pip install -r requirements.txt
   ```
3. (Optional) Copy `.env.example` to `.env` and set `WEB_SECRET` for production. For automation you need Chrome/Chromium and can set `CHROME_USER_DATA_DIR` for a persistent profile.
4. Run the site: `python run_web.py` (or `uvicorn web.app:app --host 0.0.0.0 --port 8000`).
5. Open http://localhost:8000 → Sign up → Profile (set Google + casino logins) → Dashboard (Start loop or Run now).

To run **without** Chrome/automation (UI only), set `WEB_WORKER_ENABLED=0` in `.env`.

# Website features

- **Login / Sign up** — Create an account; sessions use signed cookies.
- **Profile** — Save your **Google** email/password (for “Sign in with Google” casinos) and **casino** credentials (e.g. STAKE, CHANCED) as `username:password` per casino.
- **Dashboard** — See loop status (on/off), **Start loop** / **Stop loop** buttons, **Run now** (select a casino and run one claim), and a **2FA** form when a run is waiting for your code. Recent runs are listed.
- **History** — Full list of your runs (success, error, or info) with timestamps.
- **Automation** — When the loop is on, the app runs your universal casinos (from `casinos_universal.json`) on a schedule using your profile credentials. Results and 2FA prompts appear on the dashboard.

Universal casinos are defined in **`casinos_universal.json`** (add sites with Google login without writing code). The site uses **SQLite** (`web_data.db` by default) for users, profiles, run history, and 2FA state.

# Optional: Discord bot

You can also run the project as a Discord bot (same automation, different interface). See [discordBot.md](discordBot.md) to create a bot. Set `DISCORD_TOKEN` and `DISCORD_CHANNEL` in `.env`, then run `python main.py` (or use Docker). The bot supports slash commands and `!` prefix; `/profile` stores credentials per user, and the loop can use `DEFAULT_PROFILE_USER_ID` to use a user’s profile.

## Slash commands (/) and /profile
You can use **slash commands** instead of `!` prefix:

- **`/start`**, **`/stop`** — Start or stop the automated casino loop.
- **`/profile`** — Set or view your credentials (stored per user in `user_profiles.json`):
  - **`/profile set_google`** — Set your Google email and password (for universal casinos, Stake, Fortune Coins).
  - **`/profile set_casino`** — Set credentials for a casino (e.g. STAKE, CHANCED). Format: `username:password`. Use **`/profile list_casinos`** for valid names.
  - **`/profile list_casinos`** — List casino names you can use with `set_casino`.
  - **`/profile view`** — View your saved profile (passwords masked).
  - **`/profile clear`** — Clear google, one casino, or all.
- **`/universal <key>`** — Run a universal casino by key (uses your `/profile` Google login if set).
- **`/status`** — Show loop status, next run times, and universal casino count.
- **`/help`** — Short help.

The automated loop uses `.env` (e.g. `GOOGLE_LOGIN`) unless **`DEFAULT_PROFILE_USER_ID`** is set (Discord user ID). When set, the loop uses that user's `/profile` Google credentials for universal casinos. Your `/profile` credentials are also used when you run **`/universal`** or **`!universal`**.

## Universal casinos (any site with Google login)
You can support **any casino that offers “Sign in with Google”** without writing a new Python API. The bot loads config from **`casinos_universal.json`** and runs a generic flow: open site → click Google login (if needed) → claim daily bonus → optional countdown.

- Set **`GOOGLE_LOGIN=your@gmail.com:yourpassword`** in `.env` and run **`!auth google`** once (or use a persistent Chrome profile so the session is reused).
- Universal casinos are added to the main loop automatically. Manual check: **`!universal <key>`** (e.g. `!universal wowvegas`).
- To add a new casino: edit **`casinos_universal.json`** and add an entry with `key`, `name`, `base_url`, `use_google_login`, `google_btn_selectors`, `claim_selectors`, and optional `countdown_selector`. See the existing entries for the format. No code change required.

See **`web/README.md`** for website env vars (`WEB_SECRET`, `WEB_DATABASE_PATH`, `WEB_WORKER_ENABLED`, etc.).

# Supported Casinos 
| Casino          | Auto Claim | Countdown Timer | Backend API | Bonus (SC)            | Trusted? (payment proof) |
|-----------------|------------|-----------------|-----------------------------|------------------|---------|
| LuckyBird       |           |               | No                          | $0.25 Daily - Increases with VIP | Yes     |
| Global Poker    |           |               | No                          | $0.00-$4.00 Daily                | Yes     |
| JefeBet         |           |               | No                          | $0.20 every 6 hours              | Yes     |
| SpinQuest       |           |               | No                          | $1.00 Daily                      | Yes     |
| FortuneWheelz   |           |               | No                          | $0.20 Average Daily              | Yes     |
| Jumbo88         |           |               | No                          | Up to 5 SC Daily Spin             | Yes     |
| NoLimitCoins    |           |               | No                          | $0.20 Average Daily              | Yes     |
| Modo            |           |               | No                          | $0.30-$1.00 Daily                | Yes     |
| Stake           |           |               | Yes                         | $1.00 Daily                      | Yes     |
| Funrize         |           |               | No                          | $0.20 Average Daily              | Yes     |
| Rolling Riches  |           |               | No                          | $0.20 Daily                      | Yes     |
| American Luck   |           |               | No                          | $0.60 Average Daily              | Yes     |
| Fortune Coins   |           |               | No                          | $0.46 Average Daily              | Yes     |
| Zula            |           |               | No                          | $1.00 Daily                      | Yes     |
| Sportzino       |           |               | No                          | $0.76 Average Daily              | Yes     |
| Smiles Casino   |           |               | No                          | $0.07 Average Daily              | Yes     |
| Yay Casino      |           |               | No                          | $0.50 Average Daily              | Yes     |
| RealPrize       | IN DEVELOPMENT |           | No                          | $0.30 Daily                      | Yes     |
| LoneStar Casino | IN DEVELOPMENT |           | No                          | $0.30 Daily                      | Yes     |
| Luckyland Slots | IN DEVELOPMENT |           | No                          | $0.30-$1.00  Daily               | Yes     |
| Crown Coins     | IN DEVELOPMENT |           | Yes                         | $0.00-$2.00 Varies Daily         | Yes     |
| Goldnluck       | IN DEVELOPMENT |           | No                          | $2.00 Daily                      | No      |
| Chumba          | IN DEVELOPMENT |           | No                          | $0.25-$3.00 Daily                | Yes     |
| Chanced         | IN DEVELOPMENT |           | No                          | $0.30-$1.00 Varies Daily         | Yes     |
| iCasino         | IN DEVELOPMENT |           | No                          | $1.70 Daily                      | Yes     |
| Spin Pals       | IN DEVELOPMENT |           | No                          | $1.00  Daily                     | Yes     |
| Dara Casino     | IN DEVELOPMENT |           | No                          | $1.00  Daily                     | Yes     |
| Pulsz           | IN DEVELOPMENT |           | No                          | $0.20-$3.00 Varies Daily         | Yes     |


# Support  
Casino Claim is the only free and open source social casino claim bot.  
If you get value from this project and want to see it grow, consider sponsoring or donating via Ko-fi.  

I will do my best to push updates quickly for changes in website structure as well as overall efficiency of the bot.  
If you identify a fix, feel free to submit a pull request and I will review it.


# Stars

  <a href="https://star-history.com/#g8tsz/sweepstakes-autoclaim-&Date">
    <img src="https://api.star-history.com/svg?repos=g8tsz/sweepstakes-autoclaim-&type=Date&theme=dark" alt="Star History Chart">
  </a>


# Problem Gambling 
Gambling can become addictive. If you start feeling addicted, please seek help before it affects your life negatively. Always remember—you are not alone!

<a href="https://www.ncpgambling.org/help-treatment/"><img src="https://www.ncpgambling.org/wp-content/themes/magneti/assets/build/images/800gamb-logo-header.svg"/></a>
