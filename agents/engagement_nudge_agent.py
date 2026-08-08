"""
agents/engagement_nudge_agent.py
──────────────────────────────────
LinkedIn Engagement Nudge Agent — Fully Automated (Playwright edition)

Pipeline:
  1. Login to LinkedIn via Playwright headless browser
  2. Scrape post likers
  3. Scrape 1st-degree connections
  4. Load already-messaged log (data/messaged_users.json)
  5. Compute targets = connections − likers − already_messaged
  6. Send DMs to targets
  7. Update and save the messaged log (committed back to repo by GitHub Actions)

No Make.com. No manual setup. Fully automated.
"""

import asyncio
import time
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from integrations.linkedin_browser import LinkedInBrowser
from integrations.message_tracker import MessageTracker
from utils.logger import log_error, log_step, log_success, log_warning

console = Console(legacy_windows=False)

# Polite delay between DMs (seconds) — keeps LinkedIn happy
_DM_DELAY_SECONDS = 3.0


# ── Target computation ─────────────────────────────────────────────────────────

def compute_targets(
    connections: list[dict],
    likers: list[dict],
    tracker: MessageTracker,
) -> tuple[list[dict], int, int]:
    """
    Compute who should receive a DM.

    Targets = connections − likers − already_messaged

    Args:
        connections: All 1st-degree connections
        likers:      People who liked the post
        tracker:     MessageTracker instance (already loaded)

    Returns:
        (targets, n_liked, n_already_messaged)
    """
    # Normalise liker URLs for fast lookup
    liker_urls = {
        (p.get("profile_url") or "").split("?")[0].rstrip("/").lower()
        for p in likers
    }
    liker_urls.discard("")

    targets = []
    n_liked = 0
    n_already_messaged = 0

    for person in connections:
        norm_url = (person.get("profile_url") or "").split("?")[0].rstrip("/").lower()

        if norm_url in liker_urls:
            n_liked += 1
            continue

        if tracker.is_messaged(norm_url):
            n_already_messaged += 1
            continue

        targets.append(person)

    log_success(
        f"Targets computed: {len(targets)} to message  |  "
        f"{n_liked} already liked  |  "
        f"{n_already_messaged} already messaged previously"
    )
    return targets, n_liked, n_already_messaged


# ── Main Orchestrator ──────────────────────────────────────────────────────────

async def _run_async(
    email: str,
    password: str,
    post_url: str,
    message_template: str,
    dry_run: bool = False,
    limit: int | None = None,
    headless: bool = True,
) -> dict[str, Any]:
    """
    Async implementation of the full nudge pipeline.
    """
    # ── Load tracker (who was already messaged) ───────────────────────────────
    tracker = MessageTracker()
    tracker.load()

    if dry_run:
        # In dry-run, just use mock data — no LinkedIn login needed
        log_warning("DRY RUN — using mock data, no LinkedIn login")
        likers = _mock_likers()
        connections = _mock_connections()
        targets, n_liked, n_already = compute_targets(connections, likers, tracker)
        _print_targets_table(targets, message_template, post_url)
        console.print(
            f"\n[bold yellow]DRY RUN complete.[/bold yellow] "
            f"[dim]{len(targets)} DMs would be sent (limit: {limit or 'none'}).[/dim]\n"
        )
        return {
            "sent": 0, "liked": n_liked,
            "already_messaged": n_already, "errors": 0,
            "targets_preview": targets[:10],
        }

    # ── Live run — launch Playwright browser ──────────────────────────────────
    async with LinkedInBrowser(headless=headless) as li:

        # Step 1: Login
        await li.login(email, password)

        # Step 2: Fetch likers
        log_step("NUDGE AGENT", "Step 1/3 — Fetching post likers")
        likers = await li.get_post_likers(post_url)

        # Step 3: Fetch connections
        log_step("NUDGE AGENT", "Step 2/3 — Fetching 1st-degree connections")
        connections = await li.get_connections()

        # Step 4: Compute targets
        log_step("NUDGE AGENT", "Step 3/3 — Computing targets")
        targets, n_liked, n_already = compute_targets(connections, likers, tracker)

        if not targets:
            console.print(
                Panel.fit(
                    "[bold green]🎉 No new people to message![/bold green]\n"
                    f"[dim]{n_liked} liked the post  •  "
                    f"{n_already} already messaged previously[/dim]",
                    border_style="green",
                )
            )
            return {"sent": 0, "liked": n_liked, "already_messaged": n_already, "errors": 0}

        # Apply limit
        if limit and len(targets) > limit:
            log_warning(f"Applying limit: sending to first {limit} of {len(targets)} targets")
            targets = targets[:limit]

        _print_targets_table(targets, message_template, post_url)

        # Step 5: Send DMs
        sent = errors = 0
        console.print(f"\n[bold]📨 Sending DMs to {len(targets)} connections...[/bold]\n")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task_id = progress.add_task("Sending...", total=len(targets))

            for person in targets:
                name = person.get("name", "there")
                profile_url = person.get("profile_url", "")
                message = message_template.format(name=name, post_url=post_url)

                success = await li.send_dm(profile_url, message)

                if success:
                    sent += 1
                    tracker.mark_messaged(person, post_url, message)
                    progress.update(task_id, advance=1, description=f"✅ Sent → {name}")
                else:
                    errors += 1
                    progress.update(task_id, advance=1, description=f"❌ Failed → {name}")

                # Polite delay between DMs
                if person != targets[-1]:
                    await asyncio.sleep(_DM_DELAY_SECONDS)

    # ── Save tracker (GitHub Actions will commit this file) ───────────────────
    tracker.save()

    # ── Final summary ─────────────────────────────────────────────────────────
    _print_summary(sent, n_liked, n_already, errors, len(connections))
    log_success(f"Nudge complete: {sent} sent, {errors} errors")

    return {
        "sent": sent,
        "liked": n_liked,
        "already_messaged": n_already,
        "errors": errors,
    }


def run(
    email: str,
    password: str,
    post_url: str,
    message_template: str,
    dry_run: bool = False,
    limit: int | None = None,
    headless: bool = True,
) -> dict[str, Any]:
    """
    Synchronous entry point for the nudge pipeline.

    Args:
        email:            LinkedIn login email (from GitHub Secret)
        password:         LinkedIn login password (from GitHub Secret)
        post_url:         Your LinkedIn post URL
        message_template: Message text — supports {name} and {post_url}
        dry_run:          If True, show preview without logging in or sending DMs
        limit:            Max DMs to send per run (safety cap)
        headless:         Run browser in background (True for GitHub Actions)
    """
    console.print(
        Panel.fit(
            "[bold cyan]LinkedIn Engagement Nudge Agent[/bold cyan]\n"
            "[dim]Fully automated • No-double-DM guaranteed • GitHub Actions ready[/dim]",
            border_style="cyan",
            padding=(1, 4),
        )
    )

    if dry_run:
        console.print("[yellow bold]⚡ DRY RUN MODE — No DMs will be sent[/yellow bold]\n")

    return asyncio.run(
        _run_async(
            email=email,
            password=password,
            post_url=post_url,
            message_template=message_template,
            dry_run=dry_run,
            limit=limit,
            headless=headless,
        )
    )


# ── Rich UI Helpers ────────────────────────────────────────────────────────────

def _print_targets_table(targets: list[dict], message_template: str, post_url: str):
    table = Table(
        title=f"📨 People to Message — {len(targets)} connections",
        show_header=True,
        header_style="bold magenta",
        border_style="dim",
    )
    table.add_column("#", style="dim", width=4)
    table.add_column("Name", min_width=22)
    table.add_column("Profile", min_width=35, style="dim")
    table.add_column("Message Preview", min_width=40, max_width=55)

    for i, p in enumerate(targets[:50]):
        name = p.get("name", "Unknown")
        url = p.get("profile_url", "N/A")
        preview = message_template.format(name=name, post_url=post_url)[:70] + "..."
        table.add_row(str(i + 1), name, url, preview)

    if len(targets) > 50:
        table.add_row("...", f"... and {len(targets) - 50} more", "", "")

    console.print(table)


def _print_summary(sent: int, liked: int, already: int, errors: int, total: int):
    color = "green" if errors == 0 else "yellow"
    console.print(
        Panel.fit(
            f"[bold {color}]✅ Nudge Campaign Complete![/bold {color}]\n\n"
            f"  [green]📨 DMs sent this run:       {sent}[/green]\n"
            f"  [cyan]👍 Liked the post:          {liked}[/cyan]\n"
            f"  [dim]📋 Previously messaged:      {already}[/dim]\n"
            f"  [dim]🔗 Total connections scanned: {total}[/dim]\n"
            f"  [{'red' if errors else 'dim'}]❌ Errors:                  {errors}[/{'red' if errors else 'dim'}]\n\n"
            f"  [dim italic]Tracker updated → data/messaged_users.json[/dim italic]",
            border_style=color,
            padding=(1, 4),
        )
    )


# ── Mock Data (dry-run only) ───────────────────────────────────────────────────

def _mock_likers() -> list[dict]:
    return [
        {"name": "Alice Chen",   "profile_url": "https://www.linkedin.com/in/alicechen"},
        {"name": "Rahul Sharma", "profile_url": "https://www.linkedin.com/in/rahulsharma"},
        {"name": "Priya Nair",   "profile_url": "https://www.linkedin.com/in/priyanair"},
    ]


def _mock_connections() -> list[dict]:
    return [
        {"name": "Alice Chen",   "profile_url": "https://www.linkedin.com/in/alicechen"},
        {"name": "Rahul Sharma", "profile_url": "https://www.linkedin.com/in/rahulsharma"},
        {"name": "Priya Nair",   "profile_url": "https://www.linkedin.com/in/priyanair"},
        {"name": "Kiran Patel",  "profile_url": "https://www.linkedin.com/in/kiranpatel"},
        {"name": "Sneha Reddy",  "profile_url": "https://www.linkedin.com/in/snehareddy"},
        {"name": "Aditya Kumar", "profile_url": "https://www.linkedin.com/in/adityakumar"},
        {"name": "Meera Iyer",   "profile_url": "https://www.linkedin.com/in/meeraiyer"},
    ]
