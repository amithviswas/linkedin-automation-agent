"""
integrations/message_tracker.py
─────────────────────────────────
Persistent tracker to record every LinkedIn DM sent by the nudge agent.

Stores data in: data/messaged_users.json

This file is committed back to the GitHub repo after each run so the
next GitHub Actions run knows exactly who was already messaged —
ensuring no connection is ever DM'd twice for the same reason.

JSON format:
{
  "https://www.linkedin.com/in/someuser": {
    "name": "Alice Smith",
    "profile_url": "https://www.linkedin.com/in/someuser",
    "messaged_at": "2026-08-08T19:00:00",
    "post_url": "https://linkedin.com/posts/...",
    "message_sent": "please like my post ..."
  },
  ...
}
"""

import json
import os
from datetime import datetime
from pathlib import Path

from utils.logger import log_step, log_success, log_warning

# ── Storage path ───────────────────────────────────────────────────────────────
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_TRACKER_FILE = _DATA_DIR / "messaged_users.json"


class MessageTracker:
    """
    Tracks which LinkedIn connections have already been sent a nudge DM.

    Usage:
        tracker = MessageTracker()
        tracker.load()

        if not tracker.is_messaged("https://linkedin.com/in/alice"):
            # ... send DM ...
            tracker.mark_messaged(person, post_url, message_sent)

        tracker.save()  # call once at the end
    """

    def __init__(self):
        self._data: dict[str, dict] = {}

    def load(self) -> "MessageTracker":
        """Load the tracker from disk. Safe to call even if file doesn't exist."""
        _DATA_DIR.mkdir(parents=True, exist_ok=True)

        if _TRACKER_FILE.exists():
            try:
                with open(_TRACKER_FILE, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
                log_step("MESSAGE TRACKER", f"Loaded {len(self._data)} previously messaged profiles")
            except (json.JSONDecodeError, OSError) as e:
                log_warning(f"Could not read tracker file (starting fresh): {e}")
                self._data = {}
        else:
            log_step("MESSAGE TRACKER", "No tracker file found — starting fresh (no one messaged yet)")
            self._data = {}

        return self

    def save(self) -> None:
        """Persist the tracker to disk."""
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(_TRACKER_FILE, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)
        log_success(f"Tracker saved — {len(self._data)} total profiles recorded")

    def is_messaged(self, profile_url: str) -> bool:
        """
        Returns True if this profile has already been sent a nudge DM.

        Normalises the URL (strips trailing slash, query params) before checking.
        """
        key = self._normalise(profile_url)
        return key in self._data

    def mark_messaged(
        self,
        person: dict,
        post_url: str,
        message_sent: str,
    ) -> None:
        """
        Record that a DM was sent to this person.

        Args:
            person:       Dict with at least 'name' and 'profile_url'
            post_url:     The LinkedIn post they were nudged about
            message_sent: The exact message text that was sent
        """
        key = self._normalise(person.get("profile_url", ""))
        if not key:
            return

        self._data[key] = {
            "name": person.get("name", "Unknown"),
            "profile_url": key,
            "headline": person.get("headline", ""),
            "messaged_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
            "post_url": post_url,
            "message_sent": message_sent[:300],  # cap to avoid giant files
        }

    def get_all_messaged_urls(self) -> set[str]:
        """Return the set of all normalised profile URLs that have been messaged."""
        return set(self._data.keys())

    def count(self) -> int:
        """Total number of profiles tracked."""
        return len(self._data)

    def summary(self) -> list[dict]:
        """Return all tracked records sorted by most recent first."""
        return sorted(
            self._data.values(),
            key=lambda x: x.get("messaged_at", ""),
            reverse=True,
        )

    @staticmethod
    def _normalise(url: str) -> str:
        """Strip query params and trailing slashes for consistent matching."""
        if not url:
            return ""
        return url.split("?")[0].rstrip("/").lower()
