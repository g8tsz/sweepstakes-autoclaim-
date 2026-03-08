# Drake Hooks
# Casino Claim 2
# Google Auth API

import re
import os
import discord
import asyncio
import datetime as dt
from dotenv import load_dotenv
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

# Load environment variables from the .env file
load_dotenv()

# Retrieve the single login string from environment variables
google_login = os.getenv("GOOGLE_LOGIN")

# Initialize email/password safely
email, password = None, None
if google_login and ":" in google_login:
    email, password = google_login.split(":", 1)  # split once in case password has ":"


def _embed(title: str, description: str, color: int = 0x3B82F6) -> discord.Embed:
    e = discord.Embed(title=title, description=description, color=color)
    e.set_footer(text="Casino Claim")
    e.timestamp = dt.datetime.now(dt.timezone.utc)
    return e


async def google_auth(ctx, driver, channel, credentials, wait_2fa_fn=None):
    try:
        if credentials and len(credentials) == 2 and credentials[0] and credentials[1]:
            username, password = credentials
        else:
            username = email or os.getenv("GOOGLE_USERNAME")
            password = password or os.getenv("GOOGLE_PASSWORD")  # module-level password from GOOGLE_LOGIN

        # If no credentials, notify and exit
        if not username or not password:
            await channel.send(embed=_embed("Google Auth", "No Google credentials found. Set GOOGLE_LOGIN in `.env` or use `/profile set_google`.", 0xF59E0B))
            return

        # Start login process
        driver.get("https://myaccount.google.com/?utm_source=chrome-profile-chooser&pli=1")
        await asyncio.sleep(5)
        driver.get("https://accounts.google.com/o/oauth2/v2/auth/oauthchooseaccount?redirect_uri=https%3A%2F%2Fdevelopers.google.com%2Foauthplayground&prompt=consent&response_type=code&client_id=407408718192.apps.googleusercontent.com&scope=email&access_type=offline&flowName=GeneralOAuthFlow")
        await asyncio.sleep(5)

        # Locate and fill the email field
        identifierID = driver.find_element(By.ID, "identifierId")
        await asyncio.sleep(5)
        identifierID.send_keys(username)
        identifierID.send_keys(Keys.ENTER)
        await asyncio.sleep(5)

        # Locate and fill the password field
        password_field = driver.find_element(By.NAME, "Passwd")
        await asyncio.sleep(5)
        password_field.send_keys(password)
        password_field.send_keys(Keys.ENTER)
        await asyncio.sleep(5)

        # Screenshot after login attempt
        screenshot1_path = "1google_screenshot.png"
        driver.save_screenshot(screenshot1_path)
        await channel.send(file=discord.File(screenshot1_path))
        os.remove(screenshot1_path)

        await channel.send(embed=_embed("Google Auth — 2FA", "Approve 2FA to authenticate Google Account within 60 seconds.", 0x3B82F6))
        if wait_2fa_fn is not None:
            await wait_2fa_fn()
        else:
            await asyncio.sleep(60)

        # Final success message
        driver.get("https://myaccount.google.com/")
        await asyncio.sleep(5)
        await channel.send(embed=_embed("Google Auth — Success", "Google Auth successful!", 0x22C55E))

        google_screenshot_path = "google_screenshot.png"
        driver.save_screenshot(google_screenshot_path)
        await channel.send(file=discord.File(google_screenshot_path))
        os.remove(google_screenshot_path)

    except Exception as e:
        await channel.send(embed=_embed("Google Auth — Error", str(e)[:500], 0xEF4444))
    return
