# Casino Claim 
Never miss a casino bonus again! A discord app for claiming social casino bonuses.

<p>
<img src="https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54"/>
<img src="https://img.shields.io/badge/-selenium-%43B02A?style=for-the-badge&logo=selenium&logoColor=white"/>
<img src="https://img.shields.io/badge/-opencv-%235C3EE8?style=for-the-badge&logo=opencv&logoColor=white"/>
<img src="https://img.shields.io/badge/-pyautogui-%23FF6F00?style=for-the-badge&logo=python&logoColor=white"/>
<img src="https://img.shields.io/badge/-seleniumbase-%23323330?style=for-the-badge&logo=selenium&logoColor=white"/>
<img src="https://img.shields.io/badge/-requests-%232c2f33?style=for-the-badge&logo=&logoColor=white"/>
<img src="https://img.shields.io/badge/-discord.py-%232c2f33?style=for-the-badge&logo=discord&logoColor=white"/>
<img src="https://img.shields.io/badge/-docker-%232c2f33?style=for-the-badge&logo=docker&logoColor=white"/>

</p>

# About 
Casino Claim is a discord bot for claiming social casino bonuses. The bot will automatically claim your bonus, provide a countdown for the next, and authenticate if needed.

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


# Installation 
1. Install `git` for your operating system. Then, install `docker` and `docker-compose` for your operating system. You can follow this guide to install docker and docker-compose: https://docs.docker.com/get-docker/ Note: If you are using Windows, I strongly recommend docker desktop for Windows.

2. Clone this repository and cd into it:
```bash
git clone https://github.com/g8tsz/sweepstakes-autoclaim-.git
cd sweepstakes-autoclaim-
```
3. Create a discord bot and invite it to your server. You can follow this guide to create a discord bot: [guide](discordBot.md)

4. Create the .env file in the root directory of the project by editing the .env.example file and add the following:
    1. Add `DISCORD_TOKEN` and `DISCORD_CHANNEL` to your `.env` file.
    2. Add your casino login credentials by editing the .env.example file. After editing, rename the file to .env and save. 
5. run `docker compose up -d`
6. The Bot should now appear in Discord and start the 24 hour loop.


# Usage 
The bot is designed to check most casinos automatically in 2-hour intervals, with commands to check status of bonus. Some casinos only check once every 24 hours, but this can be changed with `!config` command. `!start` and `!stop` will start and stop the main loop. Running `!help` at any time provides the available commands. `!cleardatadir` command is useful for sites giving location issues, as well as sites you need to re-authenticate with.

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

## Web app (browser UI)
A **web interface** provides the same automation without Discord: sign up, set Google and casino credentials, start/stop the loop, run a casino now, and submit 2FA in the browser when prompted. From the project root:

```bash
uvicorn web.app:app --reload --host 0.0.0.0 --port 8000
```

Then open http://localhost:8000. See **`web/README.md`** for env vars and API details.


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
