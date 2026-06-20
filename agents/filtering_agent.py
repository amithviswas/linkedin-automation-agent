"""
agents/filtering_agent.py
──────────────────────────
Scores and ranks raw news items using a keyword/heuristic scoring algorithm —
no Gemini API calls needed. This makes filtering instant and rate-limit-proof.

Scoring criteria (mirrors what Gemini used to evaluate):
  - Viral potential: trending topics, surprising facts, controversy
  - Professional relevance: career impact, tools, skills
  - Innovation level: new tech, research breakthroughs, funding
  - Global & India audience fit: broad appeal + India relevance
  - Source prestige: tier-1 sources score higher
"""

import re
from typing import Any

from config.settings import TOP_STORIES_COUNT
from utils.logger import log_step, log_success, log_warning

# ── Scoring Weights ───────────────────────────────────────────────────────────
_WEIGHTS = {
    "viral_potential":       2.5,
    "professional_relevance": 2.0,
    "innovation_level":      2.0,
    "india_fit":             1.5,
    "source_prestige":       1.0,
    "recency_bonus":         1.0,
}

# ── Keyword Banks ─────────────────────────────────────────────────────────────
_VIRAL_KEYWORDS = [
    "breakthrough", "revolutionary", "game-changer", "first ever", "record",
    "billion", "trillion", "surpasses", "beats", "beats human", "raises",
    "sues", "bans", "fires", "launches", "acquires", "merges", "shuts down",
    "layoffs", "open source", "free", "open-weights", "leaked", "ban",
    "regulation", "fined", "criminal", "ai safety", "risk", "warning",
    "ipo", "valuation", "unicorn", "decacorn", "funding",
]

_PROFESSIONAL_KEYWORDS = [
    "ai", "artificial intelligence", "machine learning", "llm", "large language",
    "gpt", "gemini", "claude", "llama", "mistral", "agent", "copilot",
    "developer", "api", "open source", "model", "tool", "framework",
    "productivity", "automation", "no-code", "low-code", "saas",
    "startup", "founder", "engineer", "coding", "programming", "software",
    "data science", "computer vision", "robotics", "autonomous",
]

_INNOVATION_KEYWORDS = [
    "new", "launch", "release", "announce", "unveil", "introduce", "debut",
    "update", "upgrade", "feature", "capability", "breakthrough", "research",
    "paper", "study", "discovers", "solves", "achieves", "surpasses",
    "faster", "cheaper", "smaller", "larger", "powerful", "efficient",
    "multimodal", "reasoning", "agentic", "open-source", "open weights",
]

_INDIA_KEYWORDS = [
    "india", "indian", "bengaluru", "bangalore", "mumbai", "delhi", "hyderabad",
    "chennai", "pune", "noida", "gurgaon", "iit", "iim", "nasscom",
    "reliance", "tata", "infosys", "wipro", "hcl", "ola", "zomato",
    "flipkart", "meesho", "razorpay", "zepto", "blinkit", "byju",
    "sarvam", "krutrim", "bhashini", "india stack", "upi", "sebi",
]

# ── Source prestige tiers ─────────────────────────────────────────────────────
_TIER1_SOURCES = {
    "openai blog", "google ai blog", "anthropic blog", "deepmind blog",
    "meta ai blog", "microsoft ai blog", "huggingface blog",
    "techcrunch", "the verge", "ars technica", "wired", "mit technology review",
    "github blog", "hacker news best",
}
_TIER2_SOURCES = {
    "venturebeat", "venturebeat ai", "techcrunch ai", "engadget", "zdnet",
    "fast company tech", "the register", "9to5google", "yourstory", "inc42",
    "stack overflow blog", "dev.to", "unite.ai",
}


def _score_story(story: dict) -> dict:
    """Score a single story across all dimensions. Returns story + scores."""
    title = (story.get("title") or "").lower()
    summary = (story.get("summary") or "").lower()
    text = title + " " + summary
    source = (story.get("source") or "").lower()
    category = (story.get("category") or "").lower()

    def keyword_hits(keywords: list[str], weight: float = 1.0) -> float:
        hits = sum(1 for kw in keywords if kw in text)
        return min(hits * weight, 10.0)  # cap at 10

    # ── Viral Potential (0-10) ─────────────────────────────────────────────
    viral = keyword_hits(_VIRAL_KEYWORDS, 1.5)
    viral = min(viral, 10.0)

    # ── Professional Relevance (0-10) ─────────────────────────────────────
    prof = keyword_hits(_PROFESSIONAL_KEYWORDS, 1.2)
    # Boost for AI/tech categories
    if any(cat in category for cat in ("ai", "research", "developer")):
        prof = min(prof + 2.0, 10.0)
    prof = min(prof, 10.0)

    # ── Innovation Level (0-10) ───────────────────────────────────────────
    innov = keyword_hits(_INNOVATION_KEYWORDS, 1.3)
    innov = min(innov, 10.0)

    # ── India Fit (0-10) ──────────────────────────────────────────────────
    india = keyword_hits(_INDIA_KEYWORDS, 2.0)
    india = min(india + 3.0, 10.0)  # base 3 — all tech is India-relevant

    # ── Source Prestige (0-10) ────────────────────────────────────────────
    if source in _TIER1_SOURCES:
        prestige = 9.0
    elif source in _TIER2_SOURCES:
        prestige = 7.0
    else:
        prestige = 5.0

    # ── Recency Bonus (0-10) — using id as proxy (lower id = fetched earlier)
    story_id = story.get("id") or 999
    recency = max(10.0 - (story_id / 20), 2.0)  # later stories get small penalty

    # ── Composite Score (weighted average, 0–10) ──────────────────────────
    composite = (
        viral      * _WEIGHTS["viral_potential"] +
        prof       * _WEIGHTS["professional_relevance"] +
        innov      * _WEIGHTS["innovation_level"] +
        india      * _WEIGHTS["india_fit"] +
        prestige   * _WEIGHTS["source_prestige"] +
        recency    * _WEIGHTS["recency_bonus"]
    ) / sum(_WEIGHTS.values())

    return {
        **story,
        "scores": {
            "viral_potential": round(viral, 1),
            "professional_relevance": round(prof, 1),
            "innovation_level": round(innov, 1),
            "india_audience_fit": round(india, 1),
            "source_prestige": round(prestige, 1),
        },
        "composite_score": round(composite, 1),
        "why_selected": f"High scores: viral={viral:.1f}, relevance={prof:.1f}, innovation={innov:.1f}",
    }


def run(
    news_items: list[dict[str, Any]],
    top_n: int | None = None,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    """
    Filter and rank news items using keyword-based scoring.
    No Gemini API calls — instant, reliable, rate-limit-proof.

    Args:
        news_items: Raw news list from research_agent.run()
        top_n: Number of stories to select (defaults to settings.TOP_STORIES_COUNT)
        dry_run: If True, return first N items with mock scores

    Returns:
        Ranked list of top N story dicts with scores attached.
    """
    top_n = top_n or TOP_STORIES_COUNT
    log_step("FILTERING AGENT", f"Scoring {len(news_items)} stories — selecting top {top_n} (keyword scoring, no API)")

    if dry_run:
        log_warning("DRY RUN — returning first N items without scoring")
        return _mock_filter(news_items, top_n)

    if len(news_items) <= top_n:
        log_warning(f"Only {len(news_items)} items — using all without filtering")
        return _mock_filter(news_items, len(news_items))

    # ── Score all stories ─────────────────────────────────────────────────────
    scored = [_score_story(s) for s in news_items]

    # ── Sort by composite score descending ────────────────────────────────────
    scored.sort(key=lambda s: s["composite_score"], reverse=True)

    # ── Take top N and assign ranks ───────────────────────────────────────────
    top_stories = scored[:top_n]
    for i, story in enumerate(top_stories):
        story["rank"] = i + 1

    log_success(
        f"Filtering complete — top {len(top_stories)} stories selected (instant, no API)\n"
        + "\n".join(
            f"  #{s['rank']} [{s['composite_score']}] {s.get('title', 'Unknown')[:80]}"
            for s in top_stories
        )
    )
    return top_stories


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
                    "source_prestige": 8,
                },
                "composite_score": 8.0,
                "why_selected": "Mock selection for dry-run testing",
            }
        )
    return result
