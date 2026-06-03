"""
utils/helpers.py
────────────────
Shared utility functions used across agents and integrations.
"""

import json
import re
from datetime import datetime, timezone, timedelta
from typing import Any

IST = timezone(timedelta(hours=5, minutes=30))


def now_ist() -> datetime:
    """Return current datetime in IST."""
    return datetime.now(IST)


def today_str() -> str:
    """Return today's date as YYYY-MM-DD string in IST."""
    return now_ist().strftime("%Y-%m-%d")


def extract_json(text: str) -> Any:
    """
    Extract the first valid JSON object or array from a string.
    Handles cases where the model wraps JSON in markdown code fences.
    """
    # Strip markdown fences if present
    cleaned = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("```").strip()

    # Try direct parse first
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Try to find JSON block inside the text
    match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", cleaned)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError(f"No valid JSON found in model response:\n{text[:500]}")


def truncate(text: str, max_chars: int = 200) -> str:
    """Truncate a string for display purposes."""
    return text[:max_chars] + "..." if len(text) > max_chars else text


def day_of_week_content_type() -> str:
    """Return today's scheduled LinkedIn content type based on the posting strategy."""
    day = now_ist().weekday()  # 0=Mon … 6=Sun
    schedule = {
        0: "Carousel — Weekly AI roundup",
        1: "Text post — Hot take / opinion",
        2: "Short take — Quick insight",
        3: "Carousel — Tool spotlight",
        4: "Text post — What I learned this week",
        5: "Text post — Weekend insight",
        6: "Short take — Sunday reflection",
    }
    return schedule.get(day, "Text post")
