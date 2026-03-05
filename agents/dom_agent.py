"""
dom_agent.py
Extracts structured data (text, title, links) from the current browser page
using DOMTool and returns it as an ActionResponse.
"""

from __future__ import annotations

from typing import Any

from models.data_models import ActionResponse, PageContent
from agents.base_agent import BaseAgent
from config.agent_config import MAX_PAGE_TEXT_CHARS


class DOMAgent(BaseAgent):
    """
    Reads the current page source and delegates to DOMTool for extraction.
    """

    def run(self, **kwargs: Any) -> ActionResponse:
        """
        Extract page data from the currently loaded browser page.

        Returns
        -------
        ActionResponse with a :class:`~models.data_models.PageContent`
        instance serialised into ``data["page_content"]``.
        """
        url = self.browser.get_current_url()
        self._log_action(f"Extracting DOM content from {url}")

        html = self.browser.get_page_source()
        if not html:
            return ActionResponse.fail("Empty page source.", action="dom_extract")

        response = self.dom.extract_page_data(html, url=url)
        if not response.success:
            return response

        d = response.data
        # Trim text sent upstream to stay within token limits
        full_text: str = d.get("text", "")
        trimmed_text = full_text[:MAX_PAGE_TEXT_CHARS]

        page_content = PageContent(
            url=url,
            title=d.get("title", self.browser.get_title()),
            raw_text=trimmed_text,
            word_count=d.get("word_count", len(trimmed_text.split())),
            links=[lnk["href"] for lnk in d.get("links", []) if lnk.get("href")],
        )
        self._log_action(
            f"Extracted {page_content.word_count} words and "
            f"{len(page_content.links)} links"
        )
        return ActionResponse.ok({"page_content": page_content}, action="dom_extract")
