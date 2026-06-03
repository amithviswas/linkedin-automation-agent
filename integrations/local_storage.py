"""
integrations/local_storage.py
──────────────────────────────
Local file system fallback storage used when Google Sheets is not configured.
Saves each run's output as:
  - posts_output/YYYY-MM-DD/posts.json   ← all 5 posts (full data)
  - posts_output/YYYY-MM-DD/post_1.txt   ← text post ready to copy-paste
  - posts_output/YYYY-MM-DD/carousel_1.txt ← carousel script
  - posts_output/YYYY-MM-DD/summary.md   ← human-readable daily summary
"""

import json
import textwrap
from pathlib import Path
from typing import Any

from config.settings import LOCAL_STORAGE_PATH
from utils.helpers import today_str
from utils.logger import log_step, log_success, logger


def save_posts(generated_content: list[dict[str, Any]]) -> Path:
    """
    Save all generated content to local files.
    Returns the output directory path.
    """
    log_step("LOCAL STORAGE", f"Saving {len(generated_content)} posts to disk")

    output_dir = Path(LOCAL_STORAGE_PATH) / today_str()
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Full JSON dump
    full_json_path = output_dir / "posts.json"
    full_json_path.write_text(
        json.dumps(generated_content, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # 2. Individual post text files + carousel scripts
    summary_lines = [f"# LinkedIn Posts — {today_str()}\n\n"]

    for content in generated_content:
        meta = content.get("_meta", {})
        rank = meta.get("rank", "?")
        title = meta.get("story_title", "Unknown")
        text_post = content.get("text_post", {})
        carousel = content.get("carousel", {})
        short_take = content.get("short_take", {})

        # ── Text Post ──────────────────────────────────────────────────────
        post_text = text_post.get("content", "")
        post_path = output_dir / f"post_{rank}_text.txt"
        post_path.write_text(post_text, encoding="utf-8")

        # ── Carousel Script ────────────────────────────────────────────────
        carousel_lines = [f"CAROUSEL SCRIPT — {title}\n{'='*60}\n\n"]
        for slide in carousel.get("slides", []):
            num = slide.get("slide_number", "?")
            s_type = slide.get("type", "").upper()
            carousel_lines.append(f"SLIDE {num} — {s_type}\n{'-'*40}")
            if "headline" in slide:
                carousel_lines.append(f"Headline: {slide['headline']}")
            if "subtext" in slide:
                carousel_lines.append(f"Subtext:  {slide['subtext']}")
            if "body" in slide:
                carousel_lines.append(f"Body:\n{slide['body']}")
            if "sub_actions" in slide:
                carousel_lines.append("Actions:\n" + "\n".join(f"  • {a}" for a in slide["sub_actions"]))
            if "design_note" in slide:
                carousel_lines.append(f"Design:   {slide['design_note']}")
            carousel_lines.append("")

        carousel_lines.append(f"\nCAPTION:\n{carousel.get('caption', '')}")
        carousel_path = output_dir / f"post_{rank}_carousel.txt"
        carousel_path.write_text("\n".join(carousel_lines), encoding="utf-8")

        # ── Short Take ─────────────────────────────────────────────────────
        short_path = output_dir / f"post_{rank}_short.txt"
        short_path.write_text(
            f"{short_take.get('line1', '')}\n{short_take.get('line2', '')}",
            encoding="utf-8",
        )

        # ── Summary entry ──────────────────────────────────────────────────
        summary_lines.append(f"## #{rank} — {title}\n")
        summary_lines.append(f"**Source:** {meta.get('source', '')} | **Score:** {meta.get('composite_score', '')}\n")
        summary_lines.append(f"**Hook:** {text_post.get('hook', '')}\n")
        summary_lines.append(f"**Hashtags:** {' '.join(text_post.get('hashtags', []))}\n")
        summary_lines.append(f"**Files:** `post_{rank}_text.txt` | `post_{rank}_carousel.txt` | `post_{rank}_short.txt`\n")
        summary_lines.append("---\n")

    summary_path = output_dir / "summary.md"
    summary_path.write_text("\n".join(summary_lines), encoding="utf-8")

    log_success(
        f"Posts saved to: {output_dir}\n"
        f"  • posts.json (full data)\n"
        f"  • post_N_text.txt (copy-paste ready posts)\n"
        f"  • post_N_carousel.txt (carousel scripts)\n"
        f"  • summary.md (daily overview)"
    )

    return output_dir
