"""
agents/content_agent.py
────────────────────────
For each of the top N filtered stories, calls Gemini to generate three
LinkedIn content formats:
  1. Text Post  (full LinkedIn post with hook, insight, CTA, hashtags)
  2. Carousel   (6-slide script with headlines, body, design notes + caption)
  3. Short Take (2-liner punch)
"""

import json
import re
import time
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types as genai_types
from google.genai.errors import ClientError
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import GEMINI_API_KEY, GEMINI_MODEL
from utils.helpers import extract_json, today_str
from utils.logger import log_step, log_success, log_warning, logger

# ── Setup ────────────────────────────────────────────────────────────────────
_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "content_prompt.txt"


def _load_prompt(story: dict) -> str:
    template = _PROMPT_PATH.read_text(encoding="utf-8")
    return template.replace(
        "{STORY_JSON}",
        json.dumps(story, indent=2, ensure_ascii=False),
    )


def _call_gemini(prompt: str) -> str:
    """Call Gemini with smart 429 handling — waits the exact retry delay from the error."""
    for attempt in range(3):
        try:
            client = genai.Client(api_key=GEMINI_API_KEY)
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    temperature=0.85,
                    top_p=0.95,
                    max_output_tokens=8192,
                    response_mime_type="application/json",
                ),
            )
            return response.text
        except ClientError as e:
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                # Extract retry delay from error message
                delay_match = re.search(r"retry in ([\d.]+)s", err_str)
                wait_secs = float(delay_match.group(1)) + 5 if delay_match else 60
                # Check if it's a daily quota (not worth retrying today)
                if "PerDay" in err_str and attempt == 0:
                    raise RuntimeError(
                        f"Daily API quota exhausted for {GEMINI_MODEL}. "
                        f"Quota resets at midnight UTC. "
                        f"GitHub Actions will run successfully tomorrow at 8 AM IST."
                    ) from e
                logger.warning(f"Rate limited — waiting {wait_secs:.0f}s before retry {attempt+1}/3...")
                time.sleep(wait_secs)
            else:
                raise
    raise RuntimeError("Max retries exceeded on Gemini API call")


def run_for_story(story: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
    """
    Generate all 3 content formats for a single story.

    Args:
        story: A filtered story dict from filtering_agent.run()
        dry_run: If True, return mock content

    Returns:
        Content dict with text_post, carousel, short_take fields.
    """
    title = story.get("title", "Unknown")
    story_id = story.get("id", 0)

    logger.info(f"  Generating content for story #{story_id}: {title[:60]}...")

    if dry_run:
        return _mock_content(story)

    prompt = _load_prompt(story)

    try:
        raw_response = _call_gemini(prompt)
        logger.debug(f"Raw content response (first 500 chars):\n{raw_response[:500]}")
    except Exception as e:
        raise RuntimeError(f"Content agent failed for story '{title}': {e}") from e

    try:
        content = extract_json(raw_response)
        log_success(f"  ✓ Content generated for: {title[:60]}")
        return content
    except ValueError as e:
        raise RuntimeError(f"Content agent returned invalid JSON for '{title}': {e}") from e


def run(
    filtered_stories: list[dict[str, Any]],
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    """
    Generate content for all filtered stories.

    Args:
        filtered_stories: Ranked story list from filtering_agent.run()
        dry_run: If True, return mock content for all stories

    Returns:
        List of content dicts, one per story, in the same rank order.
    """
    log_step("CONTENT AGENT", f"Generating 3 content formats for {len(filtered_stories)} stories")

    results = []
    for story in filtered_stories:
        content = run_for_story(story, dry_run=dry_run)
        # Attach metadata for Sheets storage
        content["_meta"] = {
            "rank": story.get("rank", 0),
            "story_title": story.get("title", ""),
            "source": story.get("source", ""),
            "url": story.get("url", ""),
            "category": story.get("category", ""),
            "composite_score": story.get("composite_score", 0),
            "generated_date": today_str(),
        }
        results.append(content)

    log_success(f"Content generation complete — {len(results)} posts ready")
    return results


def _mock_content(story: dict) -> dict:
    """Return mock content for dry-run testing."""
    title = story.get("title", "Mock Story")
    return {
        "story_id": story.get("id", 1),
        "story_title": title,
        "text_post": {
            "content": (
                f"🔥 {title}\n\n"
                "This is a mock LinkedIn text post generated in dry-run mode.\n\n"
                "The real post will be written by Gemini with a scroll-stopping hook,\n"
                "punchy insights, and a strong personal opinion.\n\n"
                "Here's what this means for you as a tech professional.\n\n"
                "Would you use this? Drop your thoughts below 👇\n\n"
                "Save this post — you'll want to reference it later 🔖\n\n"
                "#AITools #Technology #Innovation #IndianTech #FutureOfWork"
            ),
            "char_count": 450,
            "hook": f"🔥 {title}",
            "hashtags": ["#AITools", "#Technology", "#Innovation", "#IndianTech", "#FutureOfWork"],
        },
        "carousel": {
            "slides": [
                {
                    "slide_number": 1,
                    "type": "hook",
                    "headline": title[:40],
                    "subtext": "What you need to know in 60 seconds",
                    "design_note": "Dark background, bold white headline, single accent colour",
                },
                {
                    "slide_number": 2,
                    "type": "what_happened",
                    "headline": "What happened?",
                    "body": story.get("summary", "A major development in tech/AI."),
                    "design_note": "Clean white card, left-aligned text",
                },
                {
                    "slide_number": 3,
                    "type": "why_it_matters",
                    "headline": "Why it matters",
                    "body": "This changes how developers and founders work. The impact is real.",
                    "design_note": "Stat as visual hero element",
                },
                {
                    "slide_number": 4,
                    "type": "how_to_use",
                    "headline": "How you can use this",
                    "body": "• Try the free tier today\n• Integrate into your workflow\n• Share with your team",
                    "design_note": "Numbered list, high contrast",
                },
                {
                    "slide_number": 5,
                    "type": "my_take",
                    "headline": "My honest take",
                    "body": "This is genuinely exciting. If you haven't tried this yet, you're falling behind.",
                    "design_note": "Pull quote style",
                },
                {
                    "slide_number": 6,
                    "type": "cta",
                    "headline": "Found this useful?",
                    "sub_actions": [
                        "Follow for daily AI + tech insights",
                        "Save this carousel for later",
                        "Comment: Which point surprised you most?",
                    ],
                    "design_note": "Brand-consistent, energetic finish",
                },
            ],
            "caption": (
                f"🧵 {title}\n\n"
                "Swipe through for the full breakdown.\n\n"
                "Save this carousel — it'll be useful 🔖\n\n"
                "#AITools #Technology #Innovation"
            ),
        },
        "short_take": {
            "line1": f"{title} — and the tech world is paying attention.",
            "line2": "This is the kind of update you should not sleep on.",
        },
        "best_posting_time": "Morning 8-9 AM IST",
        "content_type_recommendation": "Text Post",
    }
