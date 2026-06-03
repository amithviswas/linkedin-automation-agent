"""
main.py
────────
LinkedIn Automation Agent — Main Orchestrator

Runs the full pipeline:
  1. Research Agent   → fetch today's top tech/AI news
  2. Filtering Agent  → select top 5 stories by viral potential
  3. Content Agent    → generate 3 LinkedIn formats per story
  4. Google Sheets    → push all posts to queue
  5. Make.com         → trigger today's post for LinkedIn publishing

Usage:
  python main.py                  # Full run
  python main.py --dry-run        # Test without external API calls
  python main.py --dry-run --story-count 3
"""

import argparse
import sys
import traceback

# ── Windows UTF-8 fix (emoji support in terminal) ────────────────────────────
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from agents import content_agent, filtering_agent, research_agent
from config.settings import DRY_RUN, GOOGLE_SHEET_ID, MAKE_WEBHOOK_URL, TOP_STORIES_COUNT, USE_LOCAL_STORAGE
from integrations import make_webhook, sheets
from integrations import local_storage
from utils.helpers import day_of_week_content_type, now_ist, today_str
from utils.logger import log_error, log_step, log_success, log_warning, logger

console = Console(legacy_windows=False)


def print_banner():
    console.print(
        Panel.fit(
            "[bold cyan]LinkedIn Automation Agent[/bold cyan]\n"
            "[dim]Powered by Gemini 2.0 Flash + Google Search[/dim]",
            border_style="cyan",
            padding=(1, 4),
        )
    )
    console.print(
        f"[dim]📅 {today_str()}  |  "
        f"🕐 {now_ist().strftime('%I:%M %p IST')}  |  "
        f"📝 Today's format: {day_of_week_content_type()}[/dim]\n"
    )


def print_summary_table(generated_content: list[dict]):
    """Print a summary table of all generated posts."""
    table = Table(
        title="📋 Generated Post Queue",
        show_header=True,
        header_style="bold magenta",
        border_style="dim",
    )
    table.add_column("#", style="dim", width=3)
    table.add_column("Story", min_width=35, max_width=50)
    table.add_column("Type", width=12)
    table.add_column("Score", width=6)
    table.add_column("Hook", min_width=30, max_width=50)

    for content in generated_content:
        meta = content.get("_meta", {})
        text_post = content.get("text_post", {})
        hook = text_post.get("hook", "")[:50] + "..." if len(text_post.get("hook", "")) > 50 else text_post.get("hook", "")

        table.add_row(
            str(meta.get("rank", "?")),
            meta.get("story_title", "")[:50],
            content.get("content_type_recommendation", "Text Post"),
            str(meta.get("composite_score", "?")),
            hook,
        )

    console.print(table)


def build_posting_schedule(generated_content: list[dict]) -> dict[str, str]:
    """
    Map rank → scheduled posting time.
    Rank 1 posts today at 9 AM. Ranks 2-5 drip across the week.
    """
    from utils.helpers import now_ist
    base = now_ist()

    # Simple schedule: today + each subsequent day at 9 AM IST
    schedule = {}
    for content in generated_content:
        rank = content.get("_meta", {}).get("rank", 1)
        days_offset = rank - 1
        scheduled = base.replace(hour=9, minute=0, second=0, microsecond=0)
        from datetime import timedelta
        scheduled = scheduled + timedelta(days=days_offset)
        schedule[str(rank)] = scheduled.strftime("%Y-%m-%d 09:00 IST")

    return schedule


def run_pipeline(dry_run: bool = False, story_count: int = None) -> bool:
    """
    Execute the full automation pipeline.

    Returns:
        True if pipeline completed successfully, False on error.
    """
    story_count = story_count or TOP_STORIES_COUNT

    print_banner()

    if dry_run:
        console.print("[yellow bold]⚡ DRY RUN MODE — No external writes will occur[/yellow bold]\n")

    try:
        # ── Step 1: Research ─────────────────────────────────────────────────
        news_items = research_agent.run(dry_run=dry_run)
        console.print(f"[dim]  Found {len(news_items)} stories[/dim]")

        # ── Step 2: Filter ───────────────────────────────────────────────────
        filtered_stories = filtering_agent.run(
            news_items,
            top_n=story_count,
            dry_run=dry_run,
        )

        # ── Step 3: Generate Content ─────────────────────────────────────────
        generated_content = content_agent.run(filtered_stories, dry_run=dry_run)

        # ── Print Summary ────────────────────────────────────────────────────
        print_summary_table(generated_content)

        # ── Step 4: Save Posts ───────────────────────────────────────────────
        posting_schedule = build_posting_schedule(generated_content)

        if USE_LOCAL_STORAGE or not GOOGLE_SHEET_ID:
            # Save to local files (works without Google Cloud setup)
            output_dir = local_storage.save_posts(generated_content)
            console.print(f"[cyan]📁 Posts saved to: {output_dir}[/cyan]")
        else:
            # Push to Google Sheets
            sheets.push_to_queue(
                generated_content,
                posting_schedule=posting_schedule,
                dry_run=dry_run,
            )

        # ── Step 5: Trigger Make.com for Today's Post (Rank #1) ──────────────
        if generated_content:
            top_post = generated_content[0]
            if MAKE_WEBHOOK_URL:
                make_webhook.trigger_post(top_post, dry_run=dry_run)
            else:
                log_warning("MAKE_WEBHOOK_URL not configured — skipping auto-post. Add it to .env to enable LinkedIn publishing.")
                # Print the top post to console so user can manually copy-paste
                text_post = top_post.get("text_post", {})
                console.print("\n[bold cyan]📋 TODAY'S POST (copy this to LinkedIn):[/bold cyan]")
                console.print(Panel(
                    text_post.get("content", ""),
                    border_style="cyan",
                    title=f"[bold]Rank #1 — {top_post.get('_meta', {}).get('story_title', '')[:50]}[/bold]",
                ))

        # ── Done ─────────────────────────────────────────────────────────────
        storage_note = f"📁 posts_output/{today_str()}/" if (USE_LOCAL_STORAGE or not GOOGLE_SHEET_ID) else "📊 Google Sheets"
        console.print(
            Panel.fit(
                f"[bold green]✅ Pipeline complete![/bold green]\n"
                f"[dim]{len(generated_content)} posts generated  •  "
                f"Storage: {storage_note}  •  "
                f"{'DRY RUN' if dry_run else 'LIVE'}[/dim]",
                border_style="green",
            )
        )
        return True

    except Exception as e:
        log_error(f"Pipeline failed: {e}")
        if dry_run:
            console.print_exception()
        else:
            logger.error(traceback.format_exc())
        return False


def main():
    parser = argparse.ArgumentParser(
        description="LinkedIn Automation Agent — Gemini-powered daily content engine"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=DRY_RUN,
        help="Run pipeline without writing to Sheets or triggering Make.com",
    )
    parser.add_argument(
        "--story-count",
        type=int,
        default=TOP_STORIES_COUNT,
        help=f"Number of top stories to generate content for (default: {TOP_STORIES_COUNT})",
    )
    args = parser.parse_args()

    success = run_pipeline(dry_run=args.dry_run, story_count=args.story_count)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
