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
    Also attempts to repair truncated JSON arrays.
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

    # ── JSON Repair: handle truncated arrays ─────────────────────────────────
    # Find the start of a JSON array and try to recover complete objects
    array_start = cleaned.find("[")
    if array_start != -1:
        fragment = cleaned[array_start:]
        # Try to recover complete objects from a truncated array
        repaired = _repair_truncated_json_array(fragment)
        if repaired:
            return repaired

    raise ValueError(f"No valid JSON found in model response:\n{text[:500]}")


def _repair_truncated_json_array(fragment: str) -> Any:
    """
    Try to recover a partial JSON array by finding the last complete object.
    Returns the list of complete objects, or None if none could be recovered.
    """
    # Find all complete JSON objects using a bracket counter
    objects = []
    depth = 0
    start = None
    in_string = False
    escape_next = False

    for i, ch in enumerate(fragment):
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    obj = json.loads(fragment[start : i + 1])
                    objects.append(obj)
                except json.JSONDecodeError:
                    pass
                start = None

    return objects if objects else None


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
