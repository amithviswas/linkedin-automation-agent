"""
agents/filtering_agent.py
──────────────────────────
Takes the raw list of news items from the research agent and uses Gemini
to score each story on viral potential, professional relevance, and
India audience fit — then returns the top N ranked stories.
"""

import json
import re
import time
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types as genai_types
from google.genai.errors import ClientError, ServerError
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import GEMINI_API_KEY, GEMINI_MODEL, TOP_STORIES_COUNT
from utils.helpers import extract_json
from utils.logger import log_step, log_success, log_warning, logger

# ── Setup ────────────────────────────────────────────────────────────────────
_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "filter_prompt.txt"


def _slim_stories(stories: list[dict]) -> list[dict]:
    """Strip stories to minimal fields to keep the prompt small."""
    return [
        {
            "id": s.get("id"),
            "title": s.get("title", ""),
            "summary": s.get("summary", "")[:200],   # truncate long summaries
            "category": s.get("category", ""),
            "published_date": s.get("published_date", ""),
        }
        for s in stories
    ]


def _load_prompt(stories: list[dict], top_n: int) -> str:
    template = _PROMPT_PATH.read_text(encoding="utf-8")
    return (
        template
        .replace("{TOP_N}", str(top_n))
        .replace("{STORIES_JSON}", json.dumps(_slim_stories(stories), indent=2, ensure_ascii=False))
    )


def _call_gemini(prompt: str) -> str:
    """Call Gemini with smart retry on 429 (rate limit) and 503 (server busy)."""
    max_attempts = 7
    for attempt in range(max_attempts):
        try:
            client = genai.Client(api_key=GEMINI_API_KEY)
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    response_mime_type="application/json",
                    max_output_tokens=8192,
                ),
            )
            return response.text
        except (ClientError, ServerError) as e:
            err_str = str(e)
            # ── 500 Internal / 503 Server Busy — wait and retry ─────────────
            if "500" in err_str or "INTERNAL" in err_str or "503" in err_str or "UNAVAILABLE" in err_str:
                wait_secs = 30 + (attempt * 15)  # 30s, 45s, 60s, 75s...
                logger.warning(
                    f"Gemini server error ({err_str[:40]}) — waiting {wait_secs}s then retrying "
                    f"(attempt {attempt + 1}/{max_attempts})..."
                )
                time.sleep(wait_secs)
            # ── 429 Rate Limited — wait exact delay from API ─────────────────
            elif "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                delay_match = re.search(r"retry in ([\d.]+)s", err_str)
                if delay_match:
                    wait_secs = float(delay_match.group(1)) + 5
                    logger.warning(
                        f"Rate limited — waiting {wait_secs:.0f}s then retrying "
                        f"(attempt {attempt + 1}/{max_attempts})..."
                    )
                    time.sleep(wait_secs)
                else:
                    raise RuntimeError(
                        f"Daily API quota exhausted for model '{GEMINI_MODEL}'. "
                        f"Quota resets at midnight UTC (5:30 AM IST). "
                        f"Try again tomorrow or switch to a model with higher quota."
                    ) from e
            else:
                raise
    raise RuntimeError(f"Max retries ({max_attempts}) exceeded on Gemini API call")


def run(
    news_items: list[dict[str, Any]],
    top_n: int | None = None,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    """
    Filter and rank news items, returning the top N stories.

    Args:
        news_items: Raw news list from research_agent.run()
        top_n: Number of stories to select (defaults to settings.TOP_STORIES_COUNT)
        dry_run: If True, skip Gemini call and return first N items

    Returns:
        Ranked list of top N story dicts with scores.
    """
    top_n = top_n or TOP_STORIES_COUNT
    log_step("FILTERING AGENT", f"Scoring {len(news_items)} stories — selecting top {top_n}")

    if dry_run:
        log_warning("DRY RUN — returning first N items without scoring")
        return _mock_filter(news_items, top_n)

    if len(news_items) <= top_n:
        log_warning(f"Only {len(news_items)} items found — using all without filtering")
        return _mock_filter(news_items, len(news_items))

    # Cap at 15 stories to avoid output truncation — take the most recent ones
    candidate_stories = news_items[:15]
    prompt = _load_prompt(candidate_stories, top_n)

    try:
        raw_response = _call_gemini(prompt)
        logger.debug(f"Raw filter response (first 500 chars):\n{raw_response[:500]}")
    except Exception as e:
        raise RuntimeError(f"Filtering agent Gemini call failed: {e}") from e

    try:
        scored = extract_json(raw_response)
        if not isinstance(scored, list):
            raise ValueError("Expected a JSON array from filtering agent")

        # Build a lookup from original stories by id
        story_lookup = {str(s.get("id")): s for s in news_items}

        # Merge scores back into the original story data
        ranked_stories = []
        for item in scored:
            original_id = str(item.get("id", item.get("original_id", "")))
            original = story_lookup.get(original_id, {})
            merged = {
                **original,
                "rank": item.get("rank", len(ranked_stories) + 1),
                "scores": item.get("scores", {}),
                "composite_score": item.get("composite_score", 0),
                "why_selected": item.get("why_selected", ""),
            }
            ranked_stories.append(merged)

        log_success(
            f"Filtering complete — top {len(ranked_stories)} stories selected\n"
            + "\n".join(
                f"  #{s.get('rank')} [{s.get('composite_score', '?')}] {s.get('title', 'Unknown')}"
                for s in ranked_stories
            )
        )
        return ranked_stories
    except ValueError as e:
        raise RuntimeError(f"Filtering agent failed to return valid JSON: {e}") from e


def _mock_filter(items: list[dict], top_n: int) -> list[dict]:
    """Add mock scores and return first N items."""
    result = []
    for i, item in enumerate(items[:top_n]):
        result.append(
            {
                **item,
                "rank": i + 1,
                "scores": {
                    "viral_potential": 8,
                    "professional_relevance": 9,
                    "india_audience_fit": 7,
                    "innovation_level": 8,
                    "engagement_potential": 8,
                },
                "composite_score": 8.0,
                "why_selected": "Mock selection for dry-run testing",
            }
        )
    return result
