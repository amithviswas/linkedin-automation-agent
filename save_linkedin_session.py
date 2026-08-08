"""
save_linkedin_session.py
─────────────────────────
ONE-TIME local script: logs into LinkedIn from YOUR machine (home/work IP),
saves the browser session cookies, and encodes them for GitHub Secrets.

Run this ONCE on your local machine:
    python save_linkedin_session.py

It opens a visible Chrome window so you can complete any 2FA/CAPTCHA if needed.
After login, it saves your session and prints the command to upload it to GitHub.

The session typically lasts several weeks to months.
When it expires, just run this script again.
"""

import asyncio
import base64
import json
import os
import sys

# Windows UTF-8 fix
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("❌ Playwright not installed. Run: pip install playwright && python -m playwright install chromium")
    sys.exit(1)

SESSION_FILE = Path("linkedin_session.json")
SESSION_B64_FILE = Path("linkedin_session_b64.txt")

LINKEDIN_EMAIL    = os.getenv("LINKEDIN_EMAIL", "")
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD", "")


async def save_session():
    print("\n" + "="*60)
    print("  LinkedIn Session Saver")
    print("="*60)
    print("\nThis will open a visible Chrome window.")
    print("Log in manually if needed (2FA, CAPTCHA, etc.)")
    print("The script will detect login and save your session.\n")

    # Use credentials from .env if available
    email    = LINKEDIN_EMAIL    or input("LinkedIn Email: ").strip()
    password = LINKEDIN_PASSWORD or input("LinkedIn Password: ").strip()

    async with async_playwright() as p:
        # ── Open VISIBLE browser (not headless) ───────────────────────────────
        browser = await p.chromium.launch(
            headless=False,   # Visible so user can handle 2FA/CAPTCHA
            args=["--start-maximized"],
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()

        print("🌐 Opening LinkedIn login page...")
        await page.goto("https://www.linkedin.com/login", wait_until="networkidle", timeout=60_000)

        # Try auto-fill credentials
        try:
            await page.wait_for_selector("#username", timeout=10_000, state="visible")
            await page.fill("#username", email)
            await page.fill("#password", password)
            await page.click("button[type='submit']")
            print("✅ Credentials auto-filled. Waiting for login...")
        except Exception:
            print("⚠  Could not auto-fill credentials. Please log in manually in the browser window.")

        # ── Wait until user is logged in (feed appears) ────────────────────────
        print("\n⏳ Waiting for LinkedIn feed (up to 3 minutes)...")
        print("   If you see 2FA / CAPTCHA — complete it in the browser window.\n")

        try:
            await page.wait_for_url(
                lambda url: any(p in url for p in ["feed", "mynetwork", "jobs", "in/"]),
                timeout=180_000,  # 3 minutes — plenty of time for 2FA
            )
        except Exception:
            print("❌ Login timed out after 3 minutes. Please try again.")
            await browser.close()
            return

        print("✅ Logged in successfully!")
        await asyncio.sleep(2)

        # ── Save cookies ───────────────────────────────────────────────────────
        cookies = await context.cookies()
        storage = await page.evaluate("JSON.stringify(localStorage)")

        session_data = {
            "cookies": cookies,
            "localStorage": json.loads(storage) if storage else {},
            "url": page.url,
        }

        SESSION_FILE.write_text(json.dumps(session_data, indent=2), encoding="utf-8")
        print(f"💾 Session saved to: {SESSION_FILE.resolve()}")

        # ── Base64 encode for GitHub Secret ───────────────────────────────────
        b64 = base64.b64encode(json.dumps(session_data).encode()).decode()
        SESSION_B64_FILE.write_text(b64, encoding="utf-8")
        print(f"📦 Encoded session saved to: {SESSION_B64_FILE.resolve()}")

        await browser.close()

    # ── Print instructions ─────────────────────────────────────────────────────
    print("\n" + "="*60)
    print("  NEXT STEP — Upload to GitHub Secrets")
    print("="*60)
    print("\nRun this command to upload your session to GitHub:\n")
    print(f'  gh secret set LINKEDIN_COOKIES --body-file {SESSION_B64_FILE} --repo amithviswas/linkedin-automation-agent\n')
    print("Then trigger the GitHub Actions workflow as normal.\n")
    print("⚠  Session files contain sensitive data — do NOT commit them to git!")
    print("   (They are already in .gitignore)\n")

    # Auto-upload if gh CLI available
    answer = input("Auto-upload to GitHub Secrets now? (y/n): ").strip().lower()
    if answer == "y":
        ret = os.system(
            f'gh secret set LINKEDIN_COOKIES --body-file "{SESSION_B64_FILE}" '
            f'--repo amithviswas/linkedin-automation-agent'
        )
        if ret == 0:
            print("\n✅ LINKEDIN_COOKIES secret uploaded to GitHub!")
            print("   You can now trigger the nudge workflow — no login needed.\n")
        else:
            print("\n❌ Upload failed. Run the command above manually.\n")


if __name__ == "__main__":
    asyncio.run(save_session())
