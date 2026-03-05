"""
content_extraction_agent.py
Orchestrates DOM extraction + LLM reasoning into one tidy pipeline.
"""

from __future__ import annotations

from typing import Any, Optional

from models.data_models import ActionResponse, PageContent
from agents.base_agent import BaseAgent
from agents.dom_agent import DOMAgent
from agents.reasoning_agent import ReasoningAgent
from tools.browser_tool import BrowserTool


class ContentExtractionAgent(BaseAgent):
    """
    High-level agent that:
    1. Uses :class:`DOMAgent` to extract raw text from the current page.
    2. Passes the result to :class:`ReasoningAgent` for LLM summarisation.
    """

    def __init__(self, browser: BrowserTool) -> None:
        super().__init__(browser)
        self._dom_agent = DOMAgent(browser)
        self._reasoning_agent = ReasoningAgent(browser)

    def run(self, query: str = "", **kwargs: Any) -> ActionResponse:
        """
        Extract and summarise content from the currently loaded page.

        Parameters
        ----------
        query:
            The original user query (used to focus the LLM summary).

        Returns
        -------
        ActionResponse with ``data["page_content"]`` as a
        :class:`~models.data_models.PageContent` instance.
        """
        self._log_action("Starting content extraction pipeline")

        # Step 1: DOM extraction
        dom_response = self._dom_agent.run()
        if not dom_response.success:
            return dom_response

        page_content: PageContent = dom_response.data["page_content"]

        # Step 2: LLM reasoning / summarisation
        reason_response = self._reasoning_agent.run(
            page_content=page_content,
            query=query,
        )
        if reason_response.success:
            page_content = reason_response.data["page_content"]

        self._log_action(
            f"Extraction complete — {page_content.word_count} words, "
            f"summary length {len(page_content.summary)} chars"
        )

        # Merge action logs from sub-agents
        self._action_log.extend(self._dom_agent.get_action_log())
        self._action_log.extend(self._reasoning_agent.get_action_log())

        return ActionResponse.ok({"page_content": page_content}, action="content_extraction")
