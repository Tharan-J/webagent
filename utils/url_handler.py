"""
url_handler.py
Shortcut pipeline for when the user provides a direct URL instead of
a natural-language query.  Launches the browser, loads the page,
and returns extracted + summarised content.
"""

from __future__ import annotations

from typing import Optional

from config.agent_config import HEADLESS
from models.data_models import ActionResponse, ExecutionSummary, PageContent
from tools.browser_tool import BrowserTool
from agents.navigation_agent import NavigationAgent
from agents.captcha_agent import CaptchaAgent
from agents.content_extraction_agent import ContentExtractionAgent
from tools.logging_tool import get_logger
from utils.helpers import normalise_url

logger = get_logger(__name__)


class URLHandler:
    """
    Handles direct-URL queries end-to-end and returns an
    :class:`~models.data_models.ExecutionSummary`.
    """

    def __init__(self, headless: bool = HEADLESS) -> None:
        self.headless = headless

    def handle(self, url: str, query: str = "") -> ExecutionSummary:
        """
        Navigate to *url*, extract content, and return a summary.

        Parameters
        ----------
        url:
            The URL to load (scheme may be omitted).
        query:
            Original user query (used to focus the LLM summary).
        """
        url = normalise_url(url)
        summary = ExecutionSummary(query=query or url)
        actions: list[str] = []

        with BrowserTool(headless=self.headless) as browser:
            nav_agent = NavigationAgent(browser)
            captcha_agent = CaptchaAgent(browser)
            extraction_agent = ContentExtractionAgent(browser)

            # 1. Navigate
            nav_resp = nav_agent.run(url=url)
            actions.extend(nav_agent.get_action_log())

            if not nav_resp.success:
                summary.status = "failed"
                summary.error_message = nav_resp.error
                summary.actions_taken = actions
                return summary

            summary.final_url = browser.get_current_url()

            # 2. CAPTCHA check
            captcha_resp = captcha_agent.run()
            if not captcha_resp.success:
                summary.captcha_encountered = True
                summary.status = "failed"
                summary.error_message = "CAPTCHA on target URL — cannot extract content."
                summary.actions_taken = actions
                return summary

            # 3. Extract content
            extract_resp = extraction_agent.run(query=query)
            actions.extend(extraction_agent.get_action_log())

            if extract_resp.success:
                summary.page_content = extract_resp.data["page_content"]
                summary.status = "success"
            else:
                summary.status = "partial"
                summary.error_message = extract_resp.error

        summary.actions_taken = actions
        return summary
