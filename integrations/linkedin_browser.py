"""
integrations/linkedin_browser.py
──────────────────────────────────
Playwright-based LinkedIn browser automation.

Handles:
  - Login with email + password
  - Fetching post likers (scrapes the reactions list on a post)
  - Fetching 1st-degree connections
  - Sending a DM to a connection by profile URL

All actions include realistic human-like delays and random pauses
to reduce LinkedIn bot-detection risk.

IMPORTANT: Use conservatively — do NOT send more than 30–50 DMs/day.
"""

import asyncio
import random
import re
import time
from typing import Any

from utils.logger import log_error, log_step, log_success, log_warning

# ── Try importing Playwright (graceful error if not installed) ────────────────
try:
    from playwright.async_api import Browser, BrowserContext, Page, async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


# ── Human-like delay helpers ──────────────────────────────────────────────────

async def _human_delay(min_s: float = 1.5, max_s: float = 3.5):
    """Random pause to simulate human reading/thinking time."""
    await asyncio.sleep(random.uniform(min_s, max_s))


async def _type_like_human(page, selector: str, text: str):
    """Type text character-by-character with random delays."""
    await page.click(selector)
    await _human_delay(0.3, 0.8)
    for char in text:
        await page.keyboard.type(char)
        await asyncio.sleep(random.uniform(0.04, 0.12))


async def _scroll_down(page, times: int = 3):
    """Scroll down to load more content, simulating human scroll."""
    for _ in range(times):
        await page.evaluate("window.scrollBy(0, window.innerHeight * 0.7)")
        await _human_delay(1.0, 2.0)


# ── Main LinkedIn Browser Class ───────────────────────────────────────────────

class LinkedInBrowser:
    """
    Async context manager for LinkedIn browser automation.

    Usage:
        async with LinkedInBrowser(headless=True) as li:
            await li.login(email, password)
            likers = await li.get_post_likers(post_url)
            connections = await li.get_connections()
            await li.send_dm(profile_url, message)
    """

    def __init__(self, headless: bool = True):
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError(
                "Playwright is not installed. Run: pip install playwright && playwright install chromium"
            )
        self.headless = headless
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self.page: Page | None = None

    async def __aenter__(self):
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--disable-gpu",
                "--disable-extensions",
                "--window-size=1280,800",
                "--start-maximized",
            ],
        )
        self._context = await self._browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="en-US",
            timezone_id="Asia/Kolkata",
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        # Hide webdriver fingerprint
        await self._context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3]});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
            window.chrome = { runtime: {} };
        """)
        self.page = await self._context.new_page()
        return self

    async def __aexit__(self, *args):
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    # ── Login ────────────────────────────────────────────────────────────────

    async def login(self, email: str, password: str) -> bool:
        """
        Log into LinkedIn using explicit waits (no fragile fixed delays).

        Returns:
            True on success, raises RuntimeError on failure.
        """
        log_step("LINKEDIN BROWSER", "Navigating to LinkedIn login page...")

        # Navigate and wait for network to settle
        await self.page.goto(
            "https://www.linkedin.com/login",
            wait_until="networkidle",
            timeout=60_000,
        )
        await _human_delay(1.0, 2.0)

        # ── Wait for email field (try multiple selectors) ─────────────────────
        email_selector = None
        for sel in ["#username", "input[name='session_key']", "input[autocomplete='username']", "input[type='email']"]:
            try:
                await self.page.wait_for_selector(sel, timeout=15_000, state="visible")
                email_selector = sel
                log_step("LINKEDIN BROWSER", f"Login form found via: {sel}")
                break
            except Exception:
                continue

        if not email_selector:
            # Save screenshot for debugging
            await self.page.screenshot(path="/tmp/linkedin_login_debug.png")
            raise RuntimeError(
                "Could not find LinkedIn login form after 15s. "
                "LinkedIn may be showing a CAPTCHA or unusual page. "
                "Screenshot saved to /tmp/linkedin_login_debug.png"
            )

        # ── Fill email ────────────────────────────────────────────────────────
        log_step("LINKEDIN BROWSER", "Filling email...")
        await self.page.fill(email_selector, "")
        await _human_delay(0.3, 0.6)
        await _type_like_human(self.page, email_selector, email)
        await _human_delay(0.4, 0.9)

        # ── Wait for password field ───────────────────────────────────────────
        pass_selector = None
        for sel in ["#password", "input[name='session_password']", "input[type='password']"]:
            try:
                await self.page.wait_for_selector(sel, timeout=10_000, state="visible")
                pass_selector = sel
                break
            except Exception:
                continue

        if not pass_selector:
            raise RuntimeError("LinkedIn login form has no password field — unexpected page layout.")

        # ── Fill password ─────────────────────────────────────────────────────
        log_step("LINKEDIN BROWSER", "Filling password...")
        await self.page.fill(pass_selector, "")
        await _human_delay(0.3, 0.6)
        await _type_like_human(self.page, pass_selector, password)
        await _human_delay(0.5, 1.0)

        # ── Click Sign In ─────────────────────────────────────────────────────
        log_step("LINKEDIN BROWSER", "Submitting login form...")
        submit_clicked = False
        for sel in [
            "[data-litms-control-urn='login-submit']",
            "button[type='submit']",
            ".login__form_action_container button",
            "button:has-text('Sign in')",
        ]:
            try:
                await self.page.wait_for_selector(sel, timeout=5_000, state="visible")
                await self.page.click(sel)
                submit_clicked = True
                break
            except Exception:
                continue

        if not submit_clicked:
            # Fallback: press Enter in the password field
            await self.page.focus(pass_selector)
            await self.page.keyboard.press("Enter")

        # ── Wait for post-login redirect ──────────────────────────────────────
        try:
            await self.page.wait_for_url(
                lambda url: any(p in url for p in ["feed", "mynetwork", "jobs", "checkpoint", "challenge"]),
                timeout=30_000,
            )
        except Exception:
            pass  # URL check is best-effort; check below

        await _human_delay(1.5, 3.0)
        current_url = self.page.url
        else:
            log_success(f"Logged in (URL: {current_url})")
            return True

    # ── Get Post Likers ──────────────────────────────────────────────────────

    async def get_post_likers(self, post_url: str) -> list[dict]:
        """
        Navigate to a LinkedIn post and scrape the list of people who reacted.

        Args:
            post_url: Full LinkedIn post URL

        Returns:
            List of dicts: [{"name": "...", "profile_url": "...", "headline": "..."}]
        """
        log_step("LINKEDIN BROWSER", f"Loading post reactions: {post_url[:80]}")

        # Strip UTM params for a clean URL
        clean_url = post_url.split("?")[0].rstrip("/")
        await self.page.goto(clean_url, wait_until="domcontentloaded")
        await _human_delay(2.0, 4.0)
        await _scroll_down(self.page, 2)

        likers = []

        # Click the reactions count button to open the reactions modal
        try:
            reactions_btn = await self.page.query_selector(
                'button[aria-label*="reaction"], '
                '.social-details-social-counts__reactions-count, '
                'button.social-details-social-counts__count-value'
            )
            if reactions_btn:
                await reactions_btn.click()
                await _human_delay(2.0, 3.0)
            else:
                # Try clicking the like count text
                await self.page.click('span.social-details-social-counts__reactions')
                await _human_delay(2.0, 3.0)
        except Exception:
            log_warning("Could not open reactions modal — trying alternative selector")
            try:
                await self.page.click('[data-urn*="activity"] .social-details-social-counts')
                await _human_delay(2.0, 3.0)
            except Exception as e:
                log_warning(f"Could not open reactions modal: {e}")
                return []

        # Scroll through the reactions modal to load all likers
        for scroll_attempt in range(10):
            await _scroll_down(self.page, 1)

            # Scrape visible reactor profiles
            reactor_cards = await self.page.query_selector_all(
                '.social-details-reactors-tab__feed-update-reactions-list li, '
                '.artdeco-list__item'
            )

            for card in reactor_cards:
                try:
                    # Name
                    name_el = await card.query_selector(
                        '.react-button__text, '
                        'span.t-bold span[aria-hidden="true"], '
                        '.artdeco-entity-lockup__title span[aria-hidden="true"]'
                    )
                    name = (await name_el.inner_text()).strip() if name_el else ""

                    # Profile link
                    link_el = await card.query_selector('a[href*="/in/"]')
                    href = await link_el.get_attribute("href") if link_el else ""
                    profile_url = ""
                    if href:
                        match = re.search(r'(https://www\.linkedin\.com/in/[^/?]+)', href)
                        if match:
                            profile_url = match.group(1)
                        elif href.startswith("/in/"):
                            profile_url = "https://www.linkedin.com" + href.split("?")[0]

                    # Headline
                    headline_el = await card.query_selector(
                        '.artdeco-entity-lockup__subtitle span[aria-hidden="true"]'
                    )
                    headline = (await headline_el.inner_text()).strip() if headline_el else ""

                    if name and profile_url and not any(l["profile_url"] == profile_url for l in likers):
                        likers.append({"name": name, "profile_url": profile_url, "headline": headline})
                except Exception:
                    continue

            # Check if "Load more" button exists
            try:
                load_more = await self.page.query_selector('button.scaffold-finite-scroll__load-button')
                if load_more:
                    await load_more.click()
                    await _human_delay(1.5, 2.5)
                else:
                    break
            except Exception:
                break

        log_success(f"Found {len(likers)} likers on the post")
        return likers

    # ── Get Connections ──────────────────────────────────────────────────────

    async def get_connections(self, max_connections: int = 500) -> list[dict]:
        """
        Scrape the user's 1st-degree LinkedIn connections.

        Args:
            max_connections: Cap to avoid very long scraping sessions

        Returns:
            List of dicts: [{"name": "...", "profile_url": "...", "headline": "..."}]
        """
        log_step("LINKEDIN BROWSER", "Fetching 1st-degree connections...")
        connections = []
        page_num = 0

        while len(connections) < max_connections:
            offset = page_num * 10
            url = f"https://www.linkedin.com/mynetwork/invite-connect/connections/?start={offset}"
            await self.page.goto(url, wait_until="domcontentloaded")
            await _human_delay(2.0, 4.0)
            await _scroll_down(self.page, 3)

            cards = await self.page.query_selector_all(
                '.mn-connection-card, '
                '.scaffold-finite-scroll__content li'
            )

            if not cards:
                break

            new_found = 0
            for card in cards:
                try:
                    name_el = await card.query_selector(
                        '.mn-connection-card__name, '
                        'span.t-bold span[aria-hidden="true"]'
                    )
                    name = (await name_el.inner_text()).strip() if name_el else ""

                    link_el = await card.query_selector('a[href*="/in/"]')
                    href = await link_el.get_attribute("href") if link_el else ""
                    profile_url = ""
                    if href:
                        match = re.search(r'(/in/[^/?]+)', href)
                        if match:
                            profile_url = "https://www.linkedin.com" + match.group(1)

                    headline_el = await card.query_selector(
                        '.mn-connection-card__occupation, '
                        'span.t-14.t-black--light span[aria-hidden="true"]'
                    )
                    headline = (await headline_el.inner_text()).strip() if headline_el else ""

                    if name and profile_url and not any(c["profile_url"] == profile_url for c in connections):
                        connections.append({"name": name, "profile_url": profile_url, "headline": headline})
                        new_found += 1
                except Exception:
                    continue

            if new_found == 0:
                break  # No more connections to load

            page_num += 1
            await _human_delay(1.5, 3.0)

        log_success(f"Fetched {len(connections)} connections")
        return connections

    # ── Send DM ──────────────────────────────────────────────────────────────

    async def send_dm(self, profile_url: str, message: str) -> bool:
        """
        Send a LinkedIn DM to a connection by navigating to their profile
        and clicking the Message button.

        Args:
            profile_url: e.g. "https://www.linkedin.com/in/someuser"
            message:     The full message text to send

        Returns:
            True on success, False on failure.
        """
        clean_url = profile_url.split("?")[0].rstrip("/")
        log_step("LINKEDIN BROWSER", f"Sending DM to: {clean_url}")

        await self.page.goto(clean_url, wait_until="domcontentloaded")
        await _human_delay(2.0, 4.0)

        # Click "Message" button on the profile
        try:
            msg_btn = await self.page.query_selector(
                'button[aria-label*="Message"], '
                'a[data-control-name="message"], '
                '.pvs-profile-actions__action button:has-text("Message")'
            )
            if not msg_btn:
                # Try the "More" dropdown first
                more_btn = await self.page.query_selector(
                    'button[aria-label*="More actions"]'
                )
                if more_btn:
                    await more_btn.click()
                    await _human_delay(0.8, 1.5)
                    msg_btn = await self.page.query_selector(
                        'div[aria-label*="Message"], span:has-text("Message")'
                    )

            if not msg_btn:
                log_warning(f"No Message button found for {clean_url} — may not be a 1st-degree connection")
                return False

            await msg_btn.click()
            await _human_delay(1.5, 2.5)

        except Exception as e:
            log_error(f"Could not click Message button on {clean_url}: {e}")
            return False

        # Type the message
        try:
            msg_box = await self.page.query_selector(
                '.msg-form__contenteditable, '
                'div[contenteditable="true"][aria-label*="message"], '
                '.msg-form__msg-content-container div[contenteditable="true"]'
            )
            if not msg_box:
                log_warning(f"Message box not found for {clean_url}")
                return False

            await msg_box.click()
            await _human_delay(0.5, 1.0)

            # Type message with human-like speed
            for char in message:
                await self.page.keyboard.type(char)
                await asyncio.sleep(random.uniform(0.03, 0.08))

            await _human_delay(1.0, 2.0)

        except Exception as e:
            log_error(f"Could not type message for {clean_url}: {e}")
            return False

        # Send the message
        try:
            send_btn = await self.page.query_selector(
                'button.msg-form__send-button, '
                'button[aria-label*="Send"], '
                'button[type="submit"]:has-text("Send")'
            )
            if not send_btn:
                # Fallback: press Enter
                await self.page.keyboard.press("Enter")
            else:
                await send_btn.click()

            await _human_delay(1.5, 2.5)
            log_success(f"DM sent to {clean_url}")
            return True

        except Exception as e:
            log_error(f"Could not send message to {clean_url}: {e}")
            return False


# ── Synchronous wrapper (for non-async callers) ───────────────────────────────

def run_sync(coro):
    """Run an async coroutine synchronously."""
    return asyncio.get_event_loop().run_until_complete(coro)
