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


# ── Gemini ──────────────────────────────────────────────────────────────────
GEMINI_API_KEY: str = _optional("GEMINI_API_KEY")
GEMINI_MODEL: str = _optional("GEMINI_MODEL", "gemini-2.0-flash")

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
