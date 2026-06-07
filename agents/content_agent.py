"""
agents/content_agent.py
────────────────────────
For the top N filtered stories, calls Gemini ONCE (batch) to generate three
LinkedIn content formats per story:
  1. Text Post  (full LinkedIn post with hook, insight, CTA, hashtags)
  2. Carousel   (6-slide script with headlines, body, design notes + caption)
  3. Short Take (2-liner punch)

This batch approach uses only ONE API call regardless of how many stories
there are — saving quota and reducing rate-limit risk dramatically.
"""

import json
import re
import time
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types as genai_types
from google.genai.errors import ClientError, ServerError

from config.settings import GEMINI_API_KEY, GEMINI_MODEL
from utils.helpers import extract_json, today_str
from utils.logger import log_step, log_success, log_warning, logger

# ── Setup ────────────────────────────────────────────────────────────────────
_BATCH_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "content_prompt_batch.txt"
_SINGLE_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "content_prompt.txt"


def _load_batch_prompt(stories: list[dict]) -> str:
    """Load the batch prompt and inject all stories as JSON."""
    template = _BATCH_PROMPT_PATH.read_text(encoding="utf-8")
    slim_stories = [
        {
            "id": s.get("id"),
            "title": s.get("title", ""),
            "summary": s.get("summary", ""),
            "source": s.get("source", ""),
            "url": s.get("url", ""),
            "category": s.get("category", ""),
            "key_facts": s.get("key_facts", []),
            "why_selected": s.get("why_selected", ""),
            "composite_score": s.get("composite_score", 0),
        }
        for s in stories
    ]
    return template.replace("{STORIES_JSON}", json.dumps(slim_stories, indent=2, ensure_ascii=False))


def _load_single_prompt(story: dict) -> str:
    """Fallback: load the single-story prompt."""
    template = _SINGLE_PROMPT_PATH.read_text(encoding="utf-8")
    return template.replace("{STORY_JSON}", json.dumps(story, indent=2, ensure_ascii=False))


def _call_gemini(prompt: str, max_tokens: int = 32000) -> str:
    """Call Gemini with smart retry on 429 (rate limit) and 503 (server busy)."""
    max_attempts = 7
    for attempt in range(max_attempts):
        try:
            client = genai.Client(api_key=GEMINI_API_KEY)
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    temperature=0.85,
                    top_p=0.95,
                    max_output_tokens=max_tokens,
                    response_mime_type="application/json",
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
                        f"Quota resets at midnight UTC (5:30 AM IST)."
                    ) from e
            else:
                raise
    raise RuntimeError(f"Max retries ({max_attempts}) exceeded on Gemini API call")


def run(
    filtered_stories: list[dict[str, Any]],
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    """
    Generate all 3 content formats for ALL filtered stories in ONE API call.

    Args:
        filtered_stories: Ranked story list from filtering_agent.run()
        dry_run: If True, return mock content for all stories

    Returns:
        List of content dicts, one per story, in the same rank order.
    """
    log_step("CONTENT AGENT", f"Generating 3 content formats for {len(filtered_stories)} stories (batch mode)")

    if dry_run:
        log_warning("DRY RUN — returning mock content")
        return [_mock_content(s) for s in filtered_stories]

    # ── Try batch generation first (1 API call for all stories) ─────────────
    try:
        prompt = _load_batch_prompt(filtered_stories)
        raw_response = _call_gemini(prompt, max_tokens=32000)
        logger.debug(f"Raw batch content response (first 500 chars):\n{raw_response[:500]}")

        batch_results = extract_json(raw_response)

        if not isinstance(batch_results, list):
            raise ValueError("Batch content agent returned a non-array JSON response")

        if len(batch_results) < len(filtered_stories):
            logger.warning(
                f"Batch returned {len(batch_results)}/{len(filtered_stories)} stories — "
                f"will use mock for missing ones"
            )

        # Attach metadata to each result
        results = []
        for i, story in enumerate(filtered_stories):
            if i < len(batch_results):
                content = batch_results[i]
            else:
                logger.warning(f"  Missing content for story #{i+1}, using mock")
                content = _mock_content(story)

            content["_meta"] = {
                "rank": story.get("rank", i + 1),
                "story_title": story.get("title", ""),
                "source": story.get("source", ""),
                "url": story.get("url", ""),
                "category": story.get("category", ""),
                "composite_score": story.get("composite_score", 0),
                "generated_date": today_str(),
            }
            results.append(content)

        log_success(f"Batch content generation complete — {len(results)} posts ready (1 API call)")
        return results

    except Exception as batch_error:
        # ── Fallback: generate per-story (uses more API calls) ───────────────
        logger.warning(
            f"Batch generation failed ({batch_error}). "
            f"Falling back to per-story generation..."
        )
        return _run_per_story(filtered_stories)


def _run_per_story(filtered_stories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fallback: generate content story-by-story (uses more API calls)."""
    results = []
    for story in filtered_stories:
        title = story.get("title", "Unknown")
        story_id = story.get("id", 0)
        logger.info(f"  Generating content for story #{story_id}: {title[:60]}...")

        prompt = _load_single_prompt(story)
        try:
            raw_response = _call_gemini(prompt, max_tokens=8192)
            content = extract_json(raw_response)
            log_success(f"  ✓ Content generated for: {title[:60]}")
        except Exception as e:
            logger.warning(f"  ✗ Failed for '{title}': {e} — using mock")
            content = _mock_content(story)

        content["_meta"] = {
            "rank": story.get("rank", len(results) + 1),
            "story_title": story.get("title", ""),
            "source": story.get("source", ""),
            "url": story.get("url", ""),
            "category": story.get("category", ""),
            "composite_score": story.get("composite_score", 0),
            "generated_date": today_str(),
        }
        results.append(content)

    log_success(f"Per-story content generation complete — {len(results)} posts ready")
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
                {"slide_number": 1, "type": "hook", "headline": title[:40], "subtext": "What you need to know in 60 seconds", "design_note": "Dark background, bold white headline"},
                {"slide_number": 2, "type": "what_happened", "headline": "What happened?", "body": story.get("summary", "A major development.")[:150], "design_note": "Clean white card"},
                {"slide_number": 3, "type": "why_it_matters", "headline": "Why it matters", "body": "This changes how developers and founders work.", "design_note": "Stat as visual hero"},
                {"slide_number": 4, "type": "how_to_use", "headline": "How you can use this", "body": "• Try the free tier today\n• Integrate into your workflow\n• Share with your team", "design_note": "Numbered list"},
                {"slide_number": 5, "type": "my_take", "headline": "My honest take", "body": "This is genuinely exciting. Don't sleep on it.", "design_note": "Pull quote style"},
                {"slide_number": 6, "type": "cta", "headline": "Found this useful?", "sub_actions": ["Follow for daily AI + tech insights", "Save this carousel for later", "Comment: Which point surprised you most?"], "design_note": "Brand-consistent finish"},
            ],
            "caption": f"🧵 {title}\n\nSwipe through for the full breakdown.\n\n#AITools #Technology #Innovation",
        },
        "short_take": {
            "line1": f"{title} — and the tech world is paying attention.",
            "line2": "This is the kind of update you should not sleep on.",
        },
        "best_posting_time": "Morning 8-9 AM IST",
        "content_type_recommendation": "Text Post",
    }
