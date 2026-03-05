"""
interaction_tool.py
High-level page-interaction wrappers that delegate to BrowserTool.
Keeps interaction logic separated from the low-level browser driver.
"""

from __future__ import annotations

import time
from typing import Optional

from playwright.sync_api import TimeoutError as PWTimeoutError

from config.agent_config import SHORT_TIMEOUT_MS, BROWSER_TIMEOUT_MS
from models.data_models import ActionResponse
from tools.browser_tool import BrowserTool
from tools.logging_tool import get_logger

logger = get_logger(__name__)


class InteractionTool:
    """
    Wraps a :class:`BrowserTool` instance to provide higher-level
    interaction patterns (search, scroll, hover, wait-for-selector, …).
    """

    def __init__(self, browser: BrowserTool) -> None:
        self.browser = browser

    # ------------------------------------------------------------------
    # Waiting helpers
    # ------------------------------------------------------------------

    def wait_for_selector(
        self,
        selector: str,
        timeout_ms: int = SHORT_TIMEOUT_MS,
        state: str = "visible",
    ) -> ActionResponse:
        page = self.browser.page
        if page is None:
            return ActionResponse.fail("Browser not initialised.", action="wait_for_selector")
        try:
            page.wait_for_selector(selector, timeout=timeout_ms, state=state)
            return ActionResponse.ok({"selector": selector}, action="wait_for_selector")
        except PWTimeoutError:
            return ActionResponse.fail(
                f"Selector '{selector}' not found within {timeout_ms} ms.",
                action="wait_for_selector",
            )
        except Exception as exc:
            return ActionResponse.fail(str(exc), action="wait_for_selector")

    def wait_for_url_change(
        self,
        original_url: str,
        timeout_s: float = 8.0,
    ) -> bool:
        """
        Poll until the page URL differs from *original_url* or *timeout_s*
        elapses.  Returns True if the URL changed.
        """
        page = self.browser.page
        if page is None:
            return False
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            if page.url != original_url:
                return True
            time.sleep(0.25)
        return False

    # ------------------------------------------------------------------
    # Scrolling
    # ------------------------------------------------------------------

    def scroll_to_bottom(self) -> ActionResponse:
        page = self.browser.page
        if page is None:
            return ActionResponse.fail("Browser not initialised.", action="scroll")
        try:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(0.5)
            return ActionResponse.ok({}, action="scroll")
        except Exception as exc:
            return ActionResponse.fail(str(exc), action="scroll")

    def scroll_by(self, pixels: int = 500) -> None:
        page = self.browser.page
        if page:
            try:
                page.evaluate(f"window.scrollBy(0, {pixels})")
                time.sleep(0.3)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Search-bar interaction
    # ------------------------------------------------------------------

    def type_and_search(
        self,
        selector: str,
        query: str,
        press_enter: bool = True,
    ) -> ActionResponse:
        """
        Clear *selector*, type *query*, then press Enter (or click a submit
        button as fallback).
        """
        page = self.browser.page
        if page is None:
            return ActionResponse.fail("Browser not initialised.", action="type_and_search")

        try:
            page.wait_for_selector(selector, timeout=SHORT_TIMEOUT_MS)
            page.fill(selector, "")
            page.type(selector, query, delay=50)  # Human-like typing delay
            if press_enter:
                page.keyboard.press("Enter")
            time.sleep(1.0)
            return ActionResponse.ok({"query": query}, action="type_and_search")
        except Exception as exc:
            return ActionResponse.fail(str(exc), action="type_and_search")

    # ------------------------------------------------------------------
    # Link clicking with URL-change verification
    # ------------------------------------------------------------------

    def click_and_wait(
        self,
        href: str,
        timeout_ms: int = BROWSER_TIMEOUT_MS,
    ) -> ActionResponse:
        """
        Navigate to *href* and wait for the page to load.
        Returns ActionResponse with data["new_url"].
        """
        original_url = self.browser.get_current_url()
        response = self.browser.navigate(href)
        if not response.success:
            return response

        new_url = self.browser.get_current_url()
        url_changed = new_url != original_url
        logger.debug(
            "click_and_wait: url_changed=%s  original=%s  new=%s",
            url_changed, original_url, new_url,
        )
        response.data["new_url"] = new_url
        response.data["url_changed"] = url_changed
        return response

    # ------------------------------------------------------------------
    # Hover
    # ------------------------------------------------------------------

    def hover(self, selector: str) -> ActionResponse:
        page = self.browser.page
        if page is None:
            return ActionResponse.fail("Browser not initialised.", action="hover")
        try:
            page.hover(selector, timeout=SHORT_TIMEOUT_MS)
            return ActionResponse.ok({"selector": selector}, action="hover")
        except Exception as exc:
            return ActionResponse.fail(str(exc), action="hover")
