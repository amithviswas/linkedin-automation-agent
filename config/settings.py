"""
config/settings.py
──────────────────
Centralised configuration loader. Reads from environment variables (or a
.env file in the project root when running locally).
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root (has no effect in GitHub Actions where secrets
# are already injected as env-vars)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def _require(key: str) -> str:
    """Return env-var value or raise a clear error if missing."""
    value = os.getenv(key)
    if not value:
        raise EnvironmentError(
            f"Missing required environment variable: {key}\n"
            f"Add it to your .env file or GitHub Actions secrets."
        )
    return value


def _optional(key: str, default: str = "") -> str:
    return os.getenv(key, default)


# ── Gemini (fallback) ────────────────────────────────────────────────────────
GEMINI_API_KEY: str = _optional("GEMINI_API_KEY")
GEMINI_MODEL: str = _optional("GEMINI_MODEL", "gemini-2.0-flash")

# ── Groq (primary content engine — free, fast, reliable from GitHub Actions) ──
GROQ_API_KEY: str = _optional("GROQ_API_KEY")
GROQ_MODEL: str = _optional("GROQ_MODEL", "llama-3.3-70b-versatile")

# ── Google Sheets ────────────────────────────────────────────────────────────
GOOGLE_SHEETS_CREDS_RAW: str = _optional("GOOGLE_SHEETS_CREDS")
GOOGLE_SHEETS_CREDS: dict = json.loads(GOOGLE_SHEETS_CREDS_RAW) if GOOGLE_SHEETS_CREDS_RAW else {}
GOOGLE_SHEET_ID: str = _optional("GOOGLE_SHEET_ID")
GOOGLE_SHEET_TAB: str = _optional("GOOGLE_SHEET_TAB", "PostQueue")

# ── Make.com ─────────────────────────────────────────────────────────────────
MAKE_WEBHOOK_URL: str = _optional("MAKE_WEBHOOK_URL")

# ── Agent behaviour ──────────────────────────────────────────────────────────
DRY_RUN: bool = _optional("DRY_RUN", "false").lower() == "true"
TOP_STORIES_COUNT: int = int(_optional("TOP_STORIES_COUNT", "5"))

# ── Local Storage (fallback when Sheets not configured) ──────────────────────
USE_LOCAL_STORAGE: bool = _optional("USE_LOCAL_STORAGE", "false").lower() == "true"
LOCAL_STORAGE_PATH: str = _optional("LOCAL_STORAGE_PATH", "posts_output")

# ── LinkedIn Credentials (for Playwright browser automation) ─────────────────────
# Store these in GitHub Secrets: LINKEDIN_EMAIL, LINKEDIN_PASSWORD
# Never commit real credentials to .env in source control!
LINKEDIN_EMAIL:    str = _optional("LINKEDIN_EMAIL")
LINKEDIN_PASSWORD: str = _optional("LINKEDIN_PASSWORD")

# ── Engagement Nudge Agent Config ────────────────────────────────────────────────
# Set via GitHub Actions workflow_dispatch inputs or .env for local runs
NUDGE_POST_URL: str = _optional("NUDGE_POST_URL")   # LinkedIn post URL to check
NUDGE_MESSAGE:  str = _optional("NUDGE_MESSAGE",      # Default message template
    "please like my post {post_url}")
