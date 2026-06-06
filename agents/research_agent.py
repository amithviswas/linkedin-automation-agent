"""
agents/research_agent.py
─────────────────────────
Uses Gemini 2.0 Flash with Google Search grounding to fetch today's top
tech & AI news from across the web — 70+ stories. Returns a structured list of news items.
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
_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "research_prompt.txt"


def _load_prompt() -> str:
    template = _PROMPT_PATH.read_text(encoding="utf-8")
    return template.replace("{TODAY}", today_str())


def _call_gemini_with_search(prompt: str) -> str:
    """
    Call Gemini with Google Search grounding enabled.
    Retries on both 429 (rate limit) and 503 (server busy) errors.
    """
    max_attempts = 7
    for attempt in range(max_attempts):
        try:
            client = genai.Client(api_key=GEMINI_API_KEY)
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    tools=[genai_types.Tool(google_search=genai_types.GoogleSearch())],
                ),
            )
            return response.text
        except (ClientError, ServerError) as e:
            err_str = str(e)
            # ── 503 Server Busy — wait and retry ────────────────────────────
            if "503" in err_str or "UNAVAILABLE" in err_str:
                wait_secs = 30 + (attempt * 15)  # 30s, 45s, 60s, 75s...
                logger.warning(
                    f"Gemini server busy (503) — waiting {wait_secs}s then retrying "
                    f"(attempt {attempt + 1}/{max_attempts})..."
                )
                time.sleep(wait_secs)
            # ── 429 Rate Limited — wait exact delay from API ─────────────────
            elif "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                delay_match = re.search(r"retry in ([\d.]+)s", err_str)
                if delay_match:
                    wait_secs = float(delay_match.group(1)) + 5
                    logger.warning(
                        f"Rate limited (research) — waiting {wait_secs:.0f}s then retrying "
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
    raise RuntimeError(f"Max retries ({max_attempts}) exceeded in research agent (with grounding)")


def run(dry_run: bool = False) -> list[dict[str, Any]]:
    """
    Run the research agent.
    IMPORTANT: Only uses Google Search grounding — never falls back to
    ungrounded generation, which would produce hallucinated fake news.

    Returns:
        List of raw news item dicts (150+ items) sourced from real web search.
    """
    log_step("RESEARCH AGENT", f"Fetching today's global tech & AI news — 150+ stories from 65 sources ({today_str()})")

    if dry_run:
        log_warning("DRY RUN — returning mock research data")
        return _mock_news()

    prompt = _load_prompt()

    # ── ONLY use Google Search grounding — NEVER fall back to ungrounded ──────
    # Without grounding, Gemini hallucinates fake news stories and broken URLs.
    # It is safer to fail the pipeline than to post misinformation to LinkedIn.
    raw_response = _call_gemini_with_search(prompt)
    logger.debug(f"Raw research response (first 500 chars):\n{raw_response[:500]}")

    try:
        news_items = extract_json(raw_response)
        if not isinstance(news_items, list):
            raise ValueError("Expected a JSON array from research agent")
        log_success(f"Research complete — {len(news_items)} stories found (all sourced from real web search)")
        return news_items
    except ValueError as e:
        raise RuntimeError(f"Research agent failed to return valid JSON: {e}") from e


# ── REMOVED: _call_gemini_without_grounding ───────────────────────────────────
# This function was DANGEROUS — without Google Search grounding, Gemini
# fabricates news stories, non-existent URLs, and fake product announcements.
# Example: It invented "GPT-6 with autonomous agent mode" and posted it to LinkedIn.
# The pipeline must STOP if grounding fails, not fall back to hallucination.


def _mock_news() -> list[dict]:
    """Return mock data for dry-run / testing."""
    return [
        {
            "id": 1,
            "title": "OpenAI releases GPT-5 with real-time reasoning",
            "summary": "OpenAI has launched GPT-5, featuring advanced reasoning capabilities that can solve complex multi-step problems in real time. The model shows a 40% improvement over GPT-4o on reasoning benchmarks.",
            "source": "OpenAI Blog",
            "url": "https://openai.com/blog/gpt-5",
            "category": "AI Model",
            "published_date": today_str(),
            "key_facts": [
                "40% improvement on reasoning benchmarks",
                "Real-time reasoning mode",
                "Available via API immediately",
            ],
        },
        {
            "id": 2,
            "title": "Google launches Gemini 2.5 Ultra with 2M context window",
            "summary": "Google DeepMind released Gemini 2.5 Ultra with an unprecedented 2 million token context window, enabling processing of entire codebases in a single prompt.",
            "source": "Google Blog",
            "url": "https://blog.google/gemini-2-5-ultra",
            "category": "AI Model",
            "published_date": today_str(),
            "key_facts": [
                "2 million token context window",
                "Processes entire codebases",
                "Available on Google AI Studio",
            ],
        },
        {
            "id": 3,
            "title": "Indian startup Sarvam AI raises $41M Series A",
            "summary": "Bangalore-based Sarvam AI secured $41M in Series A funding to build AI models natively for Indian languages. The startup has trained models on 22 Indian languages.",
            "source": "TechCrunch",
            "url": "https://techcrunch.com/sarvam-ai-41m",
            "category": "Indian Tech",
            "published_date": today_str(),
            "key_facts": [
                "$41M Series A",
                "22 Indian language models",
                "Backed by Lightspeed India",
            ],
        },
        {
            "id": 4,
            "title": "GitHub Copilot now edits entire files autonomously",
            "summary": "GitHub Copilot's new agent mode can now refactor, debug, and rewrite entire files based on natural language instructions, moving beyond single-line completions.",
            "source": "GitHub Blog",
            "url": "https://github.blog/copilot-agent-mode",
            "category": "Developer",
            "published_date": today_str(),
            "key_facts": [
                "Full file editing capability",
                "Natural language instructions",
                "Available to all Copilot subscribers",
            ],
        },
        {
            "id": 5,
            "title": "ElevenLabs launches real-time voice cloning API",
            "summary": "ElevenLabs released a new API allowing developers to clone any voice in under 3 seconds with just 10 seconds of audio sample, with built-in consent verification.",
            "source": "ElevenLabs Blog",
            "url": "https://elevenlabs.io/api-launch",
            "category": "AI Tools",
            "published_date": today_str(),
            "key_facts": [
                "3-second voice cloning",
                "Needs only 10s audio sample",
                "Built-in consent system",
            ],
        },
    ]
