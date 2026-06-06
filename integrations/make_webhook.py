"""
integrations/make_webhook.py
─────────────────────────────
Sends today's top post to a Make.com webhook which then publishes
it to LinkedIn automatically.

Make.com Scenario Setup:
  Trigger: Webhooks > Custom webhook
  Action 1: LinkedIn > Create Post (using {{post_content}})
  Action 2: Google Sheets > Update Row — set Status = POSTED, Posted At = now()
"""

from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import MAKE_WEBHOOK_URL
from utils.helpers import today_str
from utils.logger import log_step, log_success, log_warning, logger

# Timeout for webhook calls
_TIMEOUT = 30.0

# ── Known hallucinated/fake topics to block ───────────────────────────────────
# These are things that do NOT exist yet. If Gemini hallucinates them,
# we catch and block the post before it goes to LinkedIn.
_HALLUCINATION_BLOCKLIST = [
    "gpt-6", "gpt-7", "gpt-8",
    "gemini 4", "gemini 5",
    "claude 4", "claude 5",
    "grok 4", "grok 5",
]


def _verify_url(url: str) -> bool:
    """
    Check that a URL actually exists and returns a valid HTTP response.
    Returns True if URL is reachable, False if broken/fake.
    """
    if not url or not url.startswith("http"):
        return False
    try:
        # Try HEAD first (faster, no body download)
        response = httpx.head(url, timeout=10.0, follow_redirects=True,
                              headers={"User-Agent": "Mozilla/5.0"})
        if response.status_code < 400:
            return True
        # HEAD blocked by server — try GET
        response = httpx.get(url, timeout=10.0, follow_redirects=True,
                             headers={"User-Agent": "Mozilla/5.0"})
        return response.status_code < 400
    except Exception:
        return False


def _contains_hallucination(post_content: str) -> str | None:
    """
    Check if post content contains known hallucinated/fake topics.
    Returns the matched phrase if found, None if content looks real.
    """
    content_lower = post_content.lower()
    for phrase in _HALLUCINATION_BLOCKLIST:
        if phrase in content_lower:
            return phrase
    return None


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=3, max=15))
def _post_to_webhook(payload: dict) -> httpx.Response:
    """Send POST request to Make.com webhook."""
    response = httpx.post(
        MAKE_WEBHOOK_URL,
        json=payload,
        timeout=_TIMEOUT,
        headers={"Content-Type": "application/json"},
    )
    response.raise_for_status()
    return response


def trigger_post(
    content: dict[str, Any],
    dry_run: bool = False,
) -> bool:
    """
    Send the top-ranked post to Make.com for LinkedIn publishing.

    Includes two safety checks before posting:
    1. Hallucination blocker — blocks posts about topics that don't exist yet
    2. URL verifier — confirms the source URL is real and reachable

    Args:
        content: The #1 ranked content dict (from content_agent.run()[0])
        dry_run: If True, skip the actual webhook call

    Returns:
        True on success
    """
    meta = content.get("_meta", {})
    text_post = content.get("text_post", {})
    carousel = content.get("carousel", {})
    short_take = content.get("short_take", {})

    story_title = meta.get("story_title", "Unknown")
    log_step("MAKE.COM", f"Triggering LinkedIn post for: {story_title[:60]}")

    payload = {
        # Core post content
        "post_content": text_post.get("content", ""),
        "post_type": content.get("content_type_recommendation", "Text Post"),
        "hashtags": text_post.get("hashtags", []),
        "hook": text_post.get("hook", ""),

        # Carousel data (if Make.com scenario handles carousel posting)
        "carousel_caption": carousel.get("caption", ""),
        "carousel_slides": carousel.get("slides", []),

        # Short take
        "short_take_line1": short_take.get("line1", ""),
        "short_take_line2": short_take.get("line2", ""),

        # Metadata
        "story_title": story_title,
        "source": meta.get("source", ""),
        "source_url": meta.get("url", ""),
        "category": meta.get("category", ""),
        "date": today_str(),
        "best_posting_time": content.get("best_posting_time", "Morning 8-9 AM IST"),
    }

    if dry_run:
        log_warning("DRY RUN — skipping Make.com webhook call")
        logger.info(f"  [DRY RUN] Payload preview:")
        logger.info(f"  Post type: {payload['post_type']}")
        logger.info(f"  Hook: {payload['hook'][:80]}")
        logger.info(f"  Content length: {len(payload['post_content'])} chars")
        return True

    if not MAKE_WEBHOOK_URL:
        log_warning("MAKE_WEBHOOK_URL not set — skipping webhook trigger")
        return False

    # ── SAFETY CHECK 1: Block known hallucinated content ──────────────────────
    hallucination = _contains_hallucination(payload["post_content"])
    if hallucination:
        raise RuntimeError(
            f"🚨 BLOCKED: Post contains likely hallucinated content ('{hallucination}'). "
            f"This topic does not exist yet. Pipeline stopped to protect your LinkedIn credibility."
        )

    # ── SAFETY CHECK 2: Verify source URL actually exists ─────────────────────
    source_url = payload.get("source_url", "")
    if source_url:
        logger.info(f"  Verifying source URL: {source_url}")
        if not _verify_url(source_url):
            raise RuntimeError(
                f"🚨 BLOCKED: Source URL is broken or unreachable: {source_url}\n"
                f"This likely means the story was hallucinated by Gemini without real grounding. "
                f"Pipeline stopped to prevent posting fake news to LinkedIn."
            )
        log_success(f"  Source URL verified ✓ {source_url}")
    else:
        log_warning("  No source URL provided — skipping URL verification")

    try:
        response = _post_to_webhook(payload)
        log_success(
            f"Make.com webhook triggered successfully "
            f"(status: {response.status_code})"
        )
        return True
    except httpx.HTTPStatusError as e:
        raise RuntimeError(
            f"Make.com webhook returned error {e.response.status_code}: {e.response.text}"
        ) from e
    except httpx.RequestError as e:
        raise RuntimeError(f"Make.com webhook request failed: {e}") from e
