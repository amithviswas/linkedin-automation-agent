"""
agents/content_agent.py
────────────────────────
Generates LinkedIn content using Groq (primary — free, fast, reliable from
GitHub Actions) with Gemini as fallback.

Groq uses Llama 3.3 70B — excellent quality for LinkedIn posts, 30 RPM free.
Gemini 2.0 Flash kept as fallback if GROQ_API_KEY is not set.
"""

import json
import re
import time
from pathlib import Path
from typing import Any

from config.settings import GEMINI_API_KEY, GEMINI_MODEL, GROQ_API_KEY, GROQ_MODEL
from utils.helpers import extract_json, today_str
from utils.logger import log_step, log_success, log_warning, logger

# ── Setup ────────────────────────────────────────────────────────────────────
_BATCH_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "content_prompt_batch.txt"
_SINGLE_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "content_prompt.txt"


def _load_batch_prompt(story: dict) -> str:
    """Load the prompt and inject a single story as JSON."""
    template = _BATCH_PROMPT_PATH.read_text(encoding="utf-8")
    slim_story = {
        "id": story.get("id"),
        "title": story.get("title", ""),
        "summary": story.get("summary", ""),
        "source": story.get("source", ""),
        "url": story.get("url", ""),
        "category": story.get("category", ""),
        "key_facts": story.get("key_facts", []),
        "why_selected": story.get("why_selected", ""),
        "composite_score": story.get("composite_score", 0),
    }
    return template.replace("{STORIES_JSON}", json.dumps(slim_story, indent=2, ensure_ascii=False))


def _load_single_prompt(story: dict) -> str:
    """Fallback: load the single-story prompt."""
    template = _SINGLE_PROMPT_PATH.read_text(encoding="utf-8")
    return template.replace("{STORY_JSON}", json.dumps(story, indent=2, ensure_ascii=False))


def _call_groq(prompt: str) -> str:
    """
    Call Groq API (primary engine).
    Free tier: 30 RPM, 14,400 RPD — works reliably from GitHub Actions.
    Model: llama-3.3-70b-versatile — excellent quality for LinkedIn posts.
    """
    from groq import Groq  # lazy import so Gemini-only users don't need groq installed
    client = Groq(api_key=GROQ_API_KEY)

    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.85,
                max_tokens=4096,
                response_format={"type": "json_object"},
            )
            return response.choices[0].message.content
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "rate_limit" in err_str.lower():
                wait = 30 * (attempt + 1)
                logger.warning(f"Groq rate limited — waiting {wait}s (attempt {attempt+1}/{max_attempts})...")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError(f"Groq: max retries exceeded")


def _call_gemini(prompt: str, max_tokens: int = 4096) -> str:
    """Fallback: Call Gemini API. Used only when GROQ_API_KEY is not set."""
    from google import genai
    from google.genai import types as genai_types
    from google.genai.errors import ClientError, ServerError

    max_attempts = 3
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
            if "503" in err_str or "UNAVAILABLE" in err_str:
                wait_secs = 30 + (attempt * 15)
                logger.warning(f"Gemini server busy — waiting {wait_secs}s (attempt {attempt+1}/{max_attempts})...")
                time.sleep(wait_secs)
            elif "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                delay_match = re.search(r"retry in ([\d.]+)s", err_str)
                wait_secs = float(delay_match.group(1)) + 5 if delay_match else 60
                logger.warning(f"Gemini rate limited — waiting {wait_secs:.0f}s (attempt {attempt+1}/{max_attempts})...")
                time.sleep(wait_secs)
            else:
                raise
    raise RuntimeError(f"Gemini: max retries exceeded")


def _call_llm(prompt: str) -> str:
    """Route to Groq (primary) or Gemini (fallback)."""
    if GROQ_API_KEY:
        logger.info("  Using Groq (llama-3.3-70b-versatile) for content generation")
        return _call_groq(prompt)
    elif GEMINI_API_KEY:
        logger.warning("  GROQ_API_KEY not set — falling back to Gemini (may be rate limited)")
        return _call_gemini(prompt)
    else:
        raise RuntimeError("No API key configured. Set GROQ_API_KEY (recommended) or GEMINI_API_KEY.")


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
    log_step("CONTENT AGENT", f"Generating LinkedIn content for top story via {'Groq' if GROQ_API_KEY else 'Gemini'}")

    if dry_run:
        log_warning("DRY RUN — returning mock content")
        return [_mock_content(s) for s in filtered_stories]

    # ── Only generate content for the TOP story (the one Make.com will post) ──
    # Generating all 5 stories = 15x more tokens. We only post story #1 anyway.
    top_story = filtered_stories[0]

    # ── Generate content (Groq primary, Gemini fallback) ─────────────────────
    try:
        prompt = _load_batch_prompt(top_story)
        raw_response = _call_llm(prompt)
        logger.debug(f"Raw content response (first 500 chars):\n{raw_response[:500]}")


        batch_results = extract_json(raw_response)

        # Unwrap list if needed — prompt returns [{...}]
        if isinstance(batch_results, list) and len(batch_results) > 0:
            content = batch_results[0]
        elif isinstance(batch_results, dict):
            content = batch_results
        else:
            raise ValueError("Content agent returned empty or invalid JSON")

        # Safety: ensure content is a dict
        if not isinstance(content, dict):
            raise ValueError(f"Unexpected content type: {type(content)}")

        # Attach metadata and fill in the remaining stories as mock
        content["_meta"] = {
            "rank": top_story.get("rank", 1),
            "story_title": top_story.get("title", ""),
            "source": top_story.get("source", ""),
            "url": top_story.get("url", ""),
            "category": top_story.get("category", ""),
            "composite_score": top_story.get("composite_score", 0),
            "generated_date": today_str(),
        }

        # Build full results list: real content for #1, mock for rest (not posted)
        results = [content]
        for story in filtered_stories[1:]:
            mock = _mock_content(story)
            mock["_meta"] = {
                "rank": story.get("rank", 0),
                "story_title": story.get("title", ""),
                "source": story.get("source", ""),
                "url": story.get("url", ""),
                "category": story.get("category", ""),
                "composite_score": story.get("composite_score", 0),
                "generated_date": today_str(),
            }
            results.append(mock)

        log_success(f"Content generation complete — top story ready (1 API call)")
        return results

    except Exception as batch_error:
        # ── Fallback: return mock for all (don't retry — already spent 5 retries + 3min wait) ──
        logger.warning(
            f"Content generation failed ({batch_error}). "
            f"Using mock content — Make.com webhook will be SKIPPED (no fake posts)."
        )
        return [_mock_content(s) for s in filtered_stories]



def _run_per_story(filtered_stories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fallback: generate content story-by-story with 2-min gaps between requests."""
    results = []
    for idx, story in enumerate(filtered_stories):
        title = story.get("title", "Unknown")
        story_id = story.get("id", 0)

        # Wait 2 minutes before each story (except the first) so rate limit resets
        if idx > 0:
            logger.info(f"  ⏳ Waiting 2 min before next story (rate limit gap)...")
            time.sleep(120)

        logger.info(f"  Generating content for story #{story_id}: {title[:60]}...")

        prompt = _load_single_prompt(story)
        try:
            raw_response = _call_gemini(prompt, max_tokens=8192)
            content = extract_json(raw_response)
            # The single-story prompt returns a JSON array [{...}] — unwrap it
            if isinstance(content, list) and len(content) > 0:
                content = content[0]
            elif isinstance(content, list):
                raise ValueError("Empty list returned by content agent")
            log_success(f"  ✓ Content generated for: {title[:60]}")
        except Exception as e:
            logger.warning(f"  ✗ Failed for '{title}': {e} — using mock")
            content = _mock_content(story)

        # Safety check — ensure content is a dict before attaching meta
        if not isinstance(content, dict):
            logger.warning(f"  Unexpected content type {type(content)} — using mock")
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
    """Return mock content for dry-run/fallback. Marked with _is_mock=True so
    main.py can detect and SKIP posting it to LinkedIn."""
    title = story.get("title", "Mock Story")
    return {
        "_is_mock": True,   # <-- blocker flag: do NOT post to LinkedIn
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
