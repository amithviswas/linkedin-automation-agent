"""
engagement_nudge.py
────────────────────
CLI entry point for the fully automated LinkedIn Engagement Nudge Agent.

Reads credentials + post config from:
  - CLI arguments (for local testing)
  - Environment variables (for GitHub Actions)

Usage (local dry-run):
  python engagement_nudge.py \\
      --post-url "https://www.linkedin.com/posts/amith-viswas-reddy_..." \\
      --message "please like my post {post_url}" \\
      --dry-run

Usage (live, from GitHub Actions via env vars — no args needed):
  LINKEDIN_EMAIL=... LINKEDIN_PASSWORD=... NUDGE_POST_URL=... NUDGE_MESSAGE=...
  python engagement_nudge.py

Template placeholders supported in --message:
  {name}     → recipient's full name (e.g. "Hey Kiran,")
  {post_url} → your LinkedIn post URL
"""

import argparse
import os
import sys
import textwrap

# ── Windows UTF-8 fix ─────────────────────────────────────────────────────────
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from rich.console import Console
from rich.panel import Panel

from agents.engagement_nudge_agent import run
from config.settings import (
    LINKEDIN_EMAIL,
    LINKEDIN_PASSWORD,
    NUDGE_MESSAGE,
    NUDGE_POST_URL,
)
from utils.logger import log_error

console = Console(legacy_windows=False)

_DEFAULT_MESSAGE = (
    "please like my post {post_url}"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="engagement_nudge",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent("""\
            LinkedIn Engagement Nudge Agent — Fully Automated
            ──────────────────────────────────────────────────
            Finds 1st-degree connections who did NOT like your post
            and haven't been messaged yet, then sends them a DM.

            Credentials can be passed as CLI args or env vars
            (LINKEDIN_EMAIL, LINKEDIN_PASSWORD, NUDGE_POST_URL, NUDGE_MESSAGE).

            Supported message placeholders:
              {name}     → recipient's full name
              {post_url} → your LinkedIn post URL
        """),
    )

    parser.add_argument("--email",    default=None, help="LinkedIn email (or set LINKEDIN_EMAIL env var)")
    parser.add_argument("--password", default=None, help="LinkedIn password (or set LINKEDIN_PASSWORD env var)")
    parser.add_argument("--post-url", default=None, metavar="URL", help="Your LinkedIn post URL")
    parser.add_argument("--message",  default=None, metavar="TEXT",
                        help="Message text. Supports {name} and {post_url} placeholders.")
    parser.add_argument("--dry-run",  action="store_true", default=False,
                        help="Preview targets without logging in or sending DMs.")
    parser.add_argument("--limit",    type=int, default=None, metavar="N",
                        help="Max DMs to send per run (recommended: 20-30 for safety).")
    parser.add_argument("--no-headless", action="store_true", default=False,
                        help="Show browser window (useful for local debugging).")

    return parser.parse_args()


def resolve_config(args: argparse.Namespace) -> tuple[str, str, str, str]:
    """
    Resolve final config values, preferring CLI args over env vars.
    Returns (email, password, post_url, message).
    """
    email    = args.email    or LINKEDIN_EMAIL    or os.getenv("LINKEDIN_EMAIL", "")
    password = args.password or LINKEDIN_PASSWORD or os.getenv("LINKEDIN_PASSWORD", "")
    post_url = args.post_url or NUDGE_POST_URL    or os.getenv("NUDGE_POST_URL", "")
    message  = args.message  or NUDGE_MESSAGE     or os.getenv("NUDGE_MESSAGE", _DEFAULT_MESSAGE)
    return email, password, post_url, message


def validate(email: str, password: str, post_url: str, dry_run: bool) -> bool:
    """Validate required config before running."""
    errors = []

    if not dry_run:
        if not email:
            errors.append("LinkedIn email is missing — set LINKEDIN_EMAIL in GitHub Secrets or pass --email")
        if not password:
            errors.append("LinkedIn password is missing — set LINKEDIN_PASSWORD in GitHub Secrets or pass --password")

    if not post_url:
        errors.append("Post URL is missing — set NUDGE_POST_URL or pass --post-url")
    elif not (post_url.startswith("https://www.linkedin.com/") or post_url.startswith("https://linkedin.com/")):
        errors.append(f"Invalid post URL: must start with https://www.linkedin.com/  (got: {post_url[:60]})")

    if errors:
        console.print(
            Panel(
                "\n".join(f"  ❌ {e}" for e in errors),
                title="[bold red]Configuration Error[/bold red]",
                border_style="red",
            )
        )
        return False

    return True


def main():
    args = parse_args()
    email, password, post_url, message = resolve_config(args)

    if not validate(email, password, post_url, args.dry_run):
        sys.exit(1)

    # ── Print run configuration ───────────────────────────────────────────────
    console.print()
    console.print(f"[bold]📎 Post URL:[/bold]  {post_url[:90]}")
    console.print(f"[bold]✉  Message:[/bold]   {message[:80]}{'...' if len(message) > 80 else ''}")
    if args.limit:
        console.print(f"[bold]🔒 Limit:[/bold]     {args.limit} DMs max per run")
    if args.dry_run:
        console.print("[bold yellow]⚡ Mode:[/bold yellow]      DRY RUN")
    else:
        console.print(f"[bold]👤 Account:[/bold]   {email}")
    console.print()

    try:
        summary = run(
            email=email,
            password=password,
            post_url=post_url,
            message_template=message,
            dry_run=args.dry_run,
            limit=args.limit,
            headless=not args.no_headless,
        )
        sys.exit(0)

    except EnvironmentError as e:
        console.print(Panel(str(e), title="[bold red]Setup Error[/bold red]", border_style="red"))
        sys.exit(1)

    except RuntimeError as e:
        console.print(Panel(str(e), title="[bold red]Runtime Error[/bold red]", border_style="red"))
        sys.exit(1)

    except Exception as e:
        log_error(f"Unexpected error: {e}")
        import traceback
        console.print_exception()
        sys.exit(1)


if __name__ == "__main__":
    main()
