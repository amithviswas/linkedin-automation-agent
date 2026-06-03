"""
utils/logger.py
───────────────
Rich-powered structured logger used across all agents and integrations.
"""

import logging
from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme

_theme = Theme(
    {
        "info": "cyan",
        "warning": "yellow",
        "error": "bold red",
        "success": "bold green",
        "agent": "bold magenta",
    }
)

console = Console(theme=_theme)

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(console=console, rich_tracebacks=True, show_path=False)],
)

logger = logging.getLogger("linkedin_agent")


def log_step(step: str, message: str) -> None:
    """Log a named pipeline step."""
    console.print(f"\n[agent]▶ [{step}][/agent]  {message}")


def log_success(message: str) -> None:
    console.print(f"[success]✓ {message}[/success]")


def log_warning(message: str) -> None:
    console.print(f"[warning]⚠ {message}[/warning]")


def log_error(message: str) -> None:
    console.print(f"[error]✗ {message}[/error]")
