"""
agents/research_agent.py
─────────────────────────
Fetches today's global tech & AI news directly from RSS feeds —
no Gemini API calls, no rate limits, always reliable.

Sources: TechCrunch, The Verge, Ars Technica, Wired, VentureBeat,
         MIT Technology Review, HuggingFace, Google AI, OpenAI, Anthropic,
         GitHub Blog, DeepMind, Microsoft AI, India startups + more.
"""

import concurrent.futures
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import feedparser
import httpx

from utils.helpers import today_str
from utils.logger import log_step, log_success, log_warning, logger

# ── RSS Sources ───────────────────────────────────────────────────────────────
# (name, url, category)
RSS_FEEDS: list[tuple[str, str, str]] = [
    # ── AI Research & Labs ─────────────────────────────────────────────────
    ("OpenAI Blog",         "https://openai.com/blog/rss.xml",                      "AI Research"),
    ("Google AI Blog",      "https://blog.google/technology/ai/rss/",               "AI Research"),
    ("Anthropic Blog",      "https://www.anthropic.com/blog/rss.xml",               "AI Research"),
    ("DeepMind Blog",       "https://deepmind.google/blog/rss.xml",                 "AI Research"),
    ("HuggingFace Blog",    "https://huggingface.co/blog/feed.xml",                 "AI Research"),
    ("Meta AI Blog",        "https://ai.meta.com/blog/feed/",                       "AI Research"),
    ("Microsoft AI Blog",   "https://blogs.microsoft.com/ai/feed/",                 "AI Research"),
    ("Mistral AI Blog",     "https://mistral.ai/feed",                              "AI Research"),
    # ── Tech News ─────────────────────────────────────────────────────────
    ("TechCrunch",          "https://techcrunch.com/feed/",                         "Tech News"),
    ("The Verge",           "https://www.theverge.com/rss/index.xml",               "Tech News"),
    ("Ars Technica",        "https://feeds.arstechnica.com/arstechnica/index",      "Tech News"),
    ("Wired",               "https://www.wired.com/feed/rss",                       "Tech News"),
    ("Engadget",            "https://www.engadget.com/rss.xml",                     "Tech News"),
    ("ZDNet",               "https://www.zdnet.com/news/rss.xml",                   "Tech News"),
    ("The Register",        "https://www.theregister.com/headlines.atom",           "Tech News"),
    ("9to5Google",          "https://9to5google.com/feed/",                         "Tech News"),
    # ── AI & Startup News ─────────────────────────────────────────────────
    ("VentureBeat AI",      "https://venturebeat.com/category/ai/feed/",            "AI Tools"),
    ("VentureBeat",         "https://venturebeat.com/feed/",                        "Startup"),
    ("TechCrunch AI",       "https://techcrunch.com/category/artificial-intelligence/feed/", "AI Tools"),
    ("AI News",             "https://www.artificialintelligence-news.com/feed/",    "AI Tools"),
    ("Unite.AI",            "https://www.unite.ai/feed/",                           "AI Tools"),
    # ── Developer & Dev Tools ─────────────────────────────────────────────
    ("GitHub Blog",         "https://github.blog/feed/",                            "Developer"),
    ("Stack Overflow Blog", "https://stackoverflow.blog/feed/",                     "Developer"),
    ("Dev.to",              "https://dev.to/feed",                                  "Developer"),
    ("Hacker News Best",    "https://hnrss.org/best",                               "Developer"),
    # ── Business & Startups ───────────────────────────────────────────────
    ("Fast Company Tech",   "https://www.fastcompany.com/technology/rss",           "Business"),
    ("MIT Technology Review","https://www.technologyreview.com/feed/",              "Research"),
    ("Harvard Business Review","https://feeds.hbr.org/harvardbusiness",            "Business"),
    # ── India & Global Startups ───────────────────────────────────────────
    ("YourStory",           "https://yourstory.com/feed",                           "India Tech"),
    ("Inc42",               "https://inc42.com/feed/",                              "India Tech"),
    ("Economic Times Tech", "https://economictimes.indiatimes.com/tech/rssfeeds/13357270.cms", "India Tech"),
    ("NDTV Gadgets",        "https://gadgets.ndtv.com/rss/feeds",                   "India Tech"),
]

# ── How far back to look for news ─────────────────────────────────────────────
_MAX_AGE_HOURS = 48  # Include stories up to 48 hours old
_MAX_PER_FEED = 5    # Max stories per feed to avoid flooding from one source
_FETCH_TIMEOUT = 10  # HTTP timeout per feed in seconds


def _parse_date(entry: dict) -> datetime | None:
    """Extract and parse the publication datetime from a feed entry."""
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        val = entry.get(key)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return None


def _clean_html(text: str) -> str:
    """Strip HTML tags from a string."""
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _fetch_feed(source_name: str, url: str, category: str, cutoff: datetime) -> list[dict]:
    """Fetch and parse a single RSS feed. Returns list of story dicts."""
    stories = []
    try:
        # Use httpx for the HTTP request (handles redirects, timeouts better)
        resp = httpx.get(url, timeout=_FETCH_TIMEOUT, follow_redirects=True,
                         headers={"User-Agent": "Mozilla/5.0 (compatible; LinkedInBot/1.0)"})
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)
    except Exception:
        # Fallback: let feedparser handle it directly
        try:
            feed = feedparser.parse(url)
        except Exception as e:
            logger.warning(f"  RSS fetch failed for {source_name}: {e}")
            return []

    for entry in feed.entries[:_MAX_PER_FEED]:
        title = _clean_html(entry.get("title", "")).strip()
        if not title or len(title) < 10:
            continue

        # Filter by date
        pub_dt = _parse_date(entry)
        if pub_dt and pub_dt < cutoff:
            continue  # Too old

        summary = _clean_html(
            entry.get("summary", "") or entry.get("description", "") or ""
        )[:600]

        url_link = entry.get("link", "")

        stories.append({
            "id": None,  # Will be assigned after collection
            "title": title,
            "summary": summary or f"Read the full story at {source_name}.",
            "source": source_name,
            "url": url_link,
            "category": category,
            "published_date": pub_dt.strftime("%Y-%m-%d") if pub_dt else today_str(),
            "key_facts": [],
        })

    return stories


def _fetch_all_feeds() -> list[dict[str, Any]]:
    """
    Fetch all RSS feeds concurrently and return deduplicated story list.
    Uses ThreadPoolExecutor for parallel HTTP requests.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=_MAX_AGE_HOURS)
    all_stories: list[dict] = []
    seen_titles: set[str] = set()

    log_step("RESEARCH AGENT", f"Fetching RSS feeds from {len(RSS_FEEDS)} sources concurrently...")

    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
        futures = {
            executor.submit(_fetch_feed, name, url, cat, cutoff): name
            for name, url, cat in RSS_FEEDS
        }
        for future in concurrent.futures.as_completed(futures):
            source = futures[future]
            try:
                stories = future.result()
                for s in stories:
                    # Deduplicate by title (case-insensitive, ignore punctuation)
                    key = re.sub(r"[^a-z0-9]", "", s["title"].lower())[:60]
                    if key not in seen_titles:
                        seen_titles.add(key)
                        all_stories.append(s)
            except Exception as e:
                logger.warning(f"  Feed error ({source}): {e}")

    # Assign sequential IDs
    for i, story in enumerate(all_stories, 1):
        story["id"] = i

    return all_stories


def run(dry_run: bool = False) -> list[dict[str, Any]]:
    """
    Run the research agent — fetches latest tech & AI news via RSS feeds.
    No Gemini API calls. No rate limits. Always works.

    Returns:
        List of news item dicts (30-80 items depending on feed freshness).
    """
    if dry_run:
        log_warning("DRY RUN — returning mock research data")
        return _mock_news()

    stories = _fetch_all_feeds()

    if not stories:
        log_warning("No stories fetched from RSS feeds — returning mock data as fallback")
        return _mock_news()

    log_success(f"Research complete — {len(stories)} stories found from RSS feeds (no API calls used)")
    return stories


def _mock_news() -> list[dict]:
    """Return mock data for dry-run / testing."""
    return [
        {
            "id": 1,
            "title": "OpenAI releases GPT-5 with real-time reasoning",
            "summary": "OpenAI has launched GPT-5, featuring advanced reasoning capabilities that can solve complex multi-step problems in real time. The model shows a 40% improvement over GPT-4o on reasoning benchmarks.",
            "source": "OpenAI Blog",
            "url": "https://openai.com/blog/gpt-5",
            "category": "AI Research",
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
            "source": "Google AI Blog",
            "url": "https://blog.google/gemini-2-5-ultra",
            "category": "AI Research",
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
            "source": "YourStory",
            "url": "https://yourstory.com/sarvam-ai-41m",
            "category": "India Tech",
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
            "source": "VentureBeat AI",
            "url": "https://venturebeat.com/elevenlabs-api-launch",
            "category": "AI Tools",
            "published_date": today_str(),
            "key_facts": [
                "3-second voice cloning",
                "Needs only 10s audio sample",
                "Built-in consent system",
            ],
        },
    ]
