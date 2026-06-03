"""
integrations/sheets.py
───────────────────────
Google Sheets integration for the LinkedIn post queue.

Sheet columns (PostQueue tab):
  A  Date
  B  Rank
  C  Story Title
  D  Source
  E  Category
  F  Composite Score
  G  Content Type
  H  Post Content (text_post or carousel caption or short_take)
  I  Hashtags
  J  Carousel Slides JSON
  K  Short Take
  L  Status          (PENDING / POSTED / SKIPPED)
  M  Scheduled Time
  N  Posted At
  O  URL
  P  Notes
"""

import json
from typing import Any

import gspread
from google.oauth2.service_account import Credentials
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import (
    GOOGLE_SHEET_ID,
    GOOGLE_SHEET_TAB,
    GOOGLE_SHEETS_CREDS,
)
from utils.helpers import now_ist, today_str
from utils.logger import log_step, log_success, log_warning, logger

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

_HEADERS = [
    "Date",
    "Rank",
    "Story Title",
    "Source",
    "Category",
    "Composite Score",
    "Content Type",
    "Post Content",
    "Hashtags",
    "Carousel Slides JSON",
    "Short Take",
    "Status",
    "Scheduled Time",
    "Posted At",
    "URL",
    "Notes",
]


def _get_client() -> gspread.Client:
    """Authenticate and return a gspread client."""
    if not GOOGLE_SHEETS_CREDS:
        raise EnvironmentError(
            "GOOGLE_SHEETS_CREDS is not set. Add your service account JSON to .env"
        )
    creds = Credentials.from_service_account_info(GOOGLE_SHEETS_CREDS, scopes=_SCOPES)
    return gspread.authorize(creds)


def _get_or_create_sheet() -> gspread.Worksheet:
    """Open the spreadsheet and return (or create) the PostQueue worksheet."""
    client = _get_client()
    spreadsheet = client.open_by_key(GOOGLE_SHEET_ID)

    try:
        worksheet = spreadsheet.worksheet(GOOGLE_SHEET_TAB)
    except gspread.WorksheetNotFound:
        logger.info(f"Creating new worksheet: {GOOGLE_SHEET_TAB}")
        worksheet = spreadsheet.add_worksheet(
            title=GOOGLE_SHEET_TAB, rows=1000, cols=len(_HEADERS)
        )
        worksheet.append_row(_HEADERS)

    # Ensure headers exist on row 1
    existing_headers = worksheet.row_values(1)
    if not existing_headers:
        worksheet.insert_row(_HEADERS, 1)

    return worksheet


def _content_to_row(content: dict[str, Any], posting_schedule: dict[str, str]) -> list:
    """Convert a content dict to a Sheets row."""
    meta = content.get("_meta", {})
    text_post = content.get("text_post", {})
    carousel = content.get("carousel", {})
    short_take = content.get("short_take", {})

    rank = meta.get("rank", 0)
    scheduled_time = posting_schedule.get(str(rank), "")

    # Primary content = text_post, fallback to carousel caption
    post_content = text_post.get("content", carousel.get("caption", ""))
    hashtags = ", ".join(text_post.get("hashtags", []))

    # Short take as single string
    short_take_str = (
        short_take.get("line1", "") + "\n" + short_take.get("line2", "")
        if short_take
        else ""
    )

    return [
        today_str(),                                          # A Date
        rank,                                                 # B Rank
        meta.get("story_title", ""),                         # C Story Title
        meta.get("source", ""),                              # D Source
        meta.get("category", ""),                            # E Category
        meta.get("composite_score", 0),                      # F Composite Score
        content.get("content_type_recommendation", "Text Post"),  # G Content Type
        post_content,                                         # H Post Content
        hashtags,                                             # I Hashtags
        json.dumps(carousel.get("slides", []), ensure_ascii=False),  # J Carousel JSON
        short_take_str,                                       # K Short Take
        "PENDING",                                            # L Status
        scheduled_time,                                       # M Scheduled Time
        "",                                                   # N Posted At
        meta.get("url", ""),                                  # O URL
        "",                                                   # P Notes
    ]


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=3, max=10))
def push_to_queue(
    generated_content: list[dict[str, Any]],
    posting_schedule: dict[str, str] | None = None,
    dry_run: bool = False,
) -> bool:
    """
    Append all generated posts to the Google Sheets post queue.

    Args:
        generated_content: List of content dicts from content_agent.run()
        posting_schedule: Dict mapping rank → scheduled_time string
        dry_run: If True, skip the actual write

    Returns:
        True on success
    """
    log_step("SHEETS", f"Pushing {len(generated_content)} posts to queue")

    if posting_schedule is None:
        posting_schedule = {}

    if dry_run:
        log_warning("DRY RUN — skipping Google Sheets write")
        for content in generated_content:
            meta = content.get("_meta", {})
            logger.info(
                f"  [DRY RUN] Would write: Rank #{meta.get('rank')} — {meta.get('story_title', '')[:50]}"
            )
        return True

    try:
        worksheet = _get_or_create_sheet()
    except Exception as e:
        raise RuntimeError(f"Failed to connect to Google Sheets: {e}") from e

    rows = []
    for content in generated_content:
        row = _content_to_row(content, posting_schedule)
        rows.append(row)

    try:
        worksheet.append_rows(rows, value_input_option="USER_ENTERED")
        log_success(
            f"Pushed {len(rows)} posts to Google Sheets ({GOOGLE_SHEET_TAB})"
        )
        return True
    except Exception as e:
        raise RuntimeError(f"Failed to write to Google Sheets: {e}") from e


def get_pending_posts(limit: int = 10) -> list[dict]:
    """
    Read pending posts from the queue (for Make.com integration or manual review).

    Returns:
        List of row dicts with PENDING status.
    """
    try:
        worksheet = _get_or_create_sheet()
        all_records = worksheet.get_all_records()
        pending = [r for r in all_records if r.get("Status") == "PENDING"]
        return pending[:limit]
    except Exception as e:
        logger.warning(f"Could not read pending posts: {e}")
        return []
