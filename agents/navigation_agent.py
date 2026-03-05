"""
navigation_agent.py
Responsible for loading a page reliably, retrying on soft failures,
and verifying the page is genuinely loaded before proceeding.
"""

from __future__ import annotations

import time
from typing import Any

from config.agent_config import BROWSER_TIMEOUT_MS
from models.data_models import ActionResponse
from agents.base_agent import BaseAgent
from tools.browser_tool import BrowserTool
from utils.helpers import normalise_url


class NavigationAgent(BaseAgent):
    """
    Navigates to a URL with retry logic and post-load verification.
    """

    MAX_RETRIES = 3
    RETRY_DELAY_S = 2.0

    def run(self, url: str = "", **kwargs: Any) -> ActionResponse:
        """
        Navigate to *url*, retrying up to MAX_RETRIES times on failure.
        Returns ActionResponse with data["final_url"].
        """
        url = normalise_url(url)
        self._log_action(f"Navigate to {url}")

        last_response: ActionResponse = ActionResponse.fail("Not attempted yet.")

        for attempt in range(1, self.MAX_RETRIES + 1):
            self.logger.info("Navigation attempt %d/%d: %s", attempt, self.MAX_RETRIES, url)
            response = self.browser.navigate(url)

            if response.success:
                final_url = self.browser.get_current_url()
                self._log_action(f"Page loaded: {final_url}")
                response.data["final_url"] = final_url
                return response

            self.logger.warning(
                "Attempt %d failed: %s — retrying in %.1f s…",
                attempt, response.error, self.RETRY_DELAY_S,
            )
            time.sleep(self.RETRY_DELAY_S)
            last_response = response

        self._log_action(f"Navigation failed after {self.MAX_RETRIES} attempts: {url}")
        return last_response

    def navigate_and_verify(self, url: str, verify_text: str = "") -> ActionResponse:
        """
        Navigate to *url* and optionally verify that *verify_text* appears
        in the page source before returning.
        """
        response = self.run(url=url)
        if not response.success:
            return response

        if verify_text:
            source = self.browser.get_page_source()
            if verify_text.lower() not in source.lower():
                return ActionResponse.fail(
                    f"Loaded page does not contain expected text: '{verify_text}'",
                    action="navigate_and_verify",
                )

        return response
