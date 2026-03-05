"""
browser_tool.py
Playwright Chromium wrapper with stealth configuration, CAPTCHA detection,
and popup/overlay removal.
"""

from __future__ import annotations

import time
from typing import Optional

from playwright.sync_api import (
    sync_playwright,
    Browser,
    BrowserContext,
    Page,
    Playwright,
    TimeoutError as PWTimeoutError,
)

from config.agent_config import (
    HEADLESS,
    BROWSER_TIMEOUT_MS,
    SHORT_TIMEOUT_MS,
    SLOW_MO_MS,
    VIEWPORT,
    USER_AGENT,
    CHROMIUM_ARGS,
)
from models.data_models import ActionResponse
from tools.logging_tool import get_logger
from utils.exceptions import BrowserInitError, NavigationError

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Init script injected into every new page context
# ---------------------------------------------------------------------------
_STEALTH_INIT_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined,
    configurable: true
});
Object.defineProperty(navigator, 'languages', {
    get: () => ['en-US', 'en'],
    configurable: true
});
Object.defineProperty(navigator, 'plugins', {
    get: () => [1, 2, 3, 4, 5],
    configurable: true
});
Object.defineProperty(navigator, 'platform', {
    get: () => 'Win32',
    configurable: true
});
window.chrome = {
    runtime: {},
    loadTimes: function() {},
    csi: function() {},
    app: {}
};
"""

# Popup/overlay removal injected after navigation
_POPUP_REMOVAL_SCRIPT = """
(function() {
    const selectors = [
        '.overlay', '.modal-backdrop', '.cookie-banner',
        '#cookie-notice', '.gdpr-banner', '.consent-banner',
        '#onetrust-banner-sdk', '.cc-window', '[class*="cookie"]',
        '[id*="cookie"]', '[class*="consent"]', '[id*="consent"]',
        '[class*="gdpr"]', '[id*="gdpr"]', '.popup-overlay',
    ];
    selectors.forEach(sel => {
        document.querySelectorAll(sel).forEach(el => {
            el.style.display = 'none';
        });
    });
    // Remove body overflow:hidden that modals often set
    document.body.style.overflow = 'auto';
    document.documentElement.style.overflow = 'auto';
})();
"""


class BrowserTool:
    """
    Manages a single Playwright Chromium session with stealth settings.

    Usage (as a context manager)::

        with BrowserTool(headless=True) as bt:
            response = bt.navigate("https://example.com")
            html = bt.get_page_source()
    """

    def __init__(self, headless: bool = HEADLESS) -> None:
        self.headless = headless
        self._pw: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self._current_url: str = ""

    # ------------------------------------------------------------------
    # Context-manager support
    # ------------------------------------------------------------------

    def __enter__(self) -> "BrowserTool":
        self._launch()
        return self

    def __exit__(self, *_) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _launch(self) -> None:
        logger.info("Launching Chromium (headless=%s)…", self.headless)
        try:
            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch(
                headless=self.headless,
                slow_mo=SLOW_MO_MS,
                args=CHROMIUM_ARGS,
            )
            self._context = self._browser.new_context(
                user_agent=USER_AGENT,
                viewport=VIEWPORT,
                locale="en-US",
                timezone_id="America/New_York",
                java_script_enabled=True,
                ignore_https_errors=True,
            )
            # Inject stealth script on every new page
            self._context.add_init_script(_STEALTH_INIT_SCRIPT)
            self.page = self._context.new_page()
            self.page.set_default_timeout(BROWSER_TIMEOUT_MS)
            logger.info("Browser launched successfully.")
        except Exception as exc:
            raise BrowserInitError(f"Failed to launch browser: {exc}") from exc

    def close(self) -> None:
        """Gracefully shut down browser and Playwright."""
        try:
            if self._browser:
                self._browser.close()
            if self._pw:
                self._pw.stop()
            logger.info("Browser closed.")
        except Exception as exc:
            logger.warning("Error closing browser: %s", exc)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def navigate(self, url: str, wait_until: str = "domcontentloaded") -> ActionResponse:
        """
        Navigate to *url* and handle common post-load tasks.

        Returns
        -------
        ActionResponse with data["url"] set to the final URL.
        """
        if self.page is None:
            return ActionResponse.fail("Browser not initialised.", action="navigate")

        logger.info("Navigating to: %s", url)
        try:
            self.page.goto(url, wait_until=wait_until, timeout=BROWSER_TIMEOUT_MS)
            self._current_url = self.page.url
            self._handle_popups()
            logger.info("Loaded: %s", self._current_url)
            return ActionResponse.ok({"url": self._current_url}, action="navigate")
        except PWTimeoutError:
            msg = f"Navigation timed out for: {url}"
            logger.warning(msg)
            return ActionResponse.fail(msg, action="navigate")
        except Exception as exc:
            msg = f"Navigation error for {url}: {exc}"
            logger.error(msg)
            return ActionResponse.fail(msg, action="navigate")

    def wait_for_load(self, timeout_ms: int = BROWSER_TIMEOUT_MS) -> None:
        """Block until networkidle or *timeout_ms* elapses."""
        try:
            self.page.wait_for_load_state("networkidle", timeout=timeout_ms)
        except PWTimeoutError:
            logger.debug("wait_for_load: networkidle timed out (acceptable).")

    # ------------------------------------------------------------------
    # Page inspection
    # ------------------------------------------------------------------

    def get_page_source(self) -> str:
        """Return the current page's full HTML source."""
        if self.page is None:
            return ""
        try:
            return self.page.content()
        except Exception as exc:
            logger.warning("get_page_source failed: %s", exc)
            return ""

    def get_current_url(self) -> str:
        if self.page:
            return self.page.url
        return self._current_url

    def get_title(self) -> str:
        if self.page:
            try:
                return self.page.title()
            except Exception:
                pass
        return ""

    # ------------------------------------------------------------------
    # CAPTCHA detection
    # ------------------------------------------------------------------

    def _is_captcha_present(self) -> bool:
        """
        Return True if the current page shows signs of a CAPTCHA.
        Checks both DOM selectors and visible text.
        """
        if self.page is None:
            return False

        # Selector-based checks
        captcha_selectors = [
            "iframe[src*='recaptcha']",
            "iframe[src*='hcaptcha']",
            "#cf-challenge-running",
            "#cf-challenge-form",
            ".g-recaptcha",
            ".h-captcha",
            "[data-sitekey]",
            "#challenge-running",
            "#challenge-form",
        ]
        for sel in captcha_selectors:
            try:
                el = self.page.query_selector(sel)
                if el:
                    logger.warning("CAPTCHA detected via selector: %s", sel)
                    return True
            except Exception:
                pass

        # Text-based checks on the visible body text
        captcha_phrases = [
            "verify you are human",
            "i am not a robot",
            "captcha",
            "unusual traffic",
            "automated requests",
            "prove you're not a robot",
            "security check",
            "cloudflare",
        ]
        try:
            body_text = self.page.inner_text("body").lower()
            for phrase in captcha_phrases:
                if phrase in body_text:
                    logger.warning("CAPTCHA detected via text phrase: '%s'", phrase)
                    return True
        except Exception:
            pass

        return False

    # ------------------------------------------------------------------
    # Popup / overlay removal
    # ------------------------------------------------------------------

    def _handle_popups(self) -> None:
        """
        After navigation: hide overlay/cookie/modal elements via JS,
        then try to click common dismiss buttons.
        """
        if self.page is None:
            return

        # 1. Inject CSS hiding script
        try:
            self.page.evaluate(_POPUP_REMOVAL_SCRIPT)
        except Exception as exc:
            logger.debug("Popup-removal script failed: %s", exc)

        # 2. Try clicking dismiss buttons
        dismiss_texts = [
            "Accept", "Accept All", "Accept Cookies",
            "I Accept", "I Agree", "Agree", "OK", "Got it",
            "Close", "Dismiss", "No thanks", "×",
        ]
        for text in dismiss_texts:
            try:
                btn = self.page.get_by_role("button", name=text, exact=False).first
                if btn.is_visible(timeout=500):
                    btn.click(timeout=1_000)
                    logger.debug("Clicked dismiss button: '%s'", text)
                    time.sleep(0.3)
                    break
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Interaction helpers (used by interaction_tool.py)
    # ------------------------------------------------------------------

    def click(self, selector: str, timeout_ms: int = SHORT_TIMEOUT_MS) -> ActionResponse:
        """Click an element identified by *selector*."""
        if self.page is None:
            return ActionResponse.fail("Browser not initialised.", action="click")
        try:
            self.page.click(selector, timeout=timeout_ms)
            return ActionResponse.ok({"selector": selector}, action="click")
        except Exception as exc:
            return ActionResponse.fail(str(exc), action="click")

    def click_link_by_href(self, href: str) -> ActionResponse:
        """Navigate directly to *href* (avoids element interaction issues)."""
        return self.navigate(href)

    def type_text(self, selector: str, text: str) -> ActionResponse:
        """Fill *selector* with *text*, clearing first."""
        if self.page is None:
            return ActionResponse.fail("Browser not initialised.", action="type")
        try:
            self.page.fill(selector, text, timeout=SHORT_TIMEOUT_MS)
            return ActionResponse.ok({"selector": selector, "text": text}, action="type")
        except Exception as exc:
            return ActionResponse.fail(str(exc), action="type")

    def press_key(self, key: str) -> ActionResponse:
        """Send a keyboard key-press to the focused element."""
        if self.page is None:
            return ActionResponse.fail("Browser not initialised.", action="press_key")
        try:
            self.page.keyboard.press(key)
            return ActionResponse.ok({"key": key}, action="press_key")
        except Exception as exc:
            return ActionResponse.fail(str(exc), action="press_key")

    def screenshot(self, path: str = "screenshot.png") -> ActionResponse:
        if self.page is None:
            return ActionResponse.fail("Browser not initialised.", action="screenshot")
        try:
            self.page.screenshot(path=path, full_page=True)
            return ActionResponse.ok({"path": path}, action="screenshot")
        except Exception as exc:
            return ActionResponse.fail(str(exc), action="screenshot")
