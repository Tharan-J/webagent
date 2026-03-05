"""
reasoning_agent.py
Uses the LLMTool to summarise, extract facts, or reason about page content.
Requires a valid GOOGLE_API_KEY in the environment.
"""

from __future__ import annotations

from typing import Any, Optional

from models.data_models import ActionResponse, PageContent
from agents.base_agent import BaseAgent
from tools.browser_tool import BrowserTool
from tools.llm_tool import LLMTool
from utils.exceptions import LLMError
from tools.logging_tool import get_logger

logger = get_logger(__name__)


class ReasoningAgent(BaseAgent):
    """
    Wraps LLMTool to enrich a :class:`PageContent` object with an
    LLM-generated summary and relevant facts.
    """

    def __init__(self, browser: BrowserTool) -> None:
        super().__init__(browser)
        try:
            self._llm = LLMTool()
            self._llm_available = True
        except LLMError as exc:
            logger.warning("LLM unavailable — summaries will be skipped.  Reason: %s", exc)
            self._llm = None  # type: ignore[assignment]
            self._llm_available = False

    # ------------------------------------------------------------------
    # BaseAgent.run interface
    # ------------------------------------------------------------------

    def run(
        self,
        page_content: Optional[PageContent] = None,
        query: str = "",
        **kwargs: Any,
    ) -> ActionResponse:
        """
        Summarise *page_content.raw_text* and optionally extract facts
        relevant to *query*.

        Returns ActionResponse with:
            ``data["summary"]``     – LLM summary text
            ``data["facts"]``       – Fact bullets (if query provided)
            ``data["page_content"]``– Updated PageContent (summary filled)
        """
        if page_content is None:
            return ActionResponse.fail("No PageContent provided.", action="reasoning")

        if not self._llm_available:
            # Fallback: return a crude extractive snippet
            snippet = page_content.raw_text[:500]
            page_content.summary = snippet
            return ActionResponse.ok(
                {"summary": snippet, "facts": "", "page_content": page_content},
                action="reasoning",
            )

        self._log_action(f"LLM summarising content from {page_content.url}")
        summary_resp = self._llm.summarise(page_content.raw_text, query=query)
        summary = (
            summary_resp.data.get("response", "")
            if summary_resp.success
            else page_content.raw_text[:500]
        )

        facts = ""
        if query:
            facts_resp = self._llm.extract_facts(page_content.raw_text, query)
            if facts_resp.success:
                facts = facts_resp.data.get("response", "")

        page_content.summary = summary
        self._log_action("LLM summary generated.")

        return ActionResponse.ok(
            {"summary": summary, "facts": facts, "page_content": page_content},
            action="reasoning",
        )

    def pick_best_url(self, urls: list[str], query: str) -> Optional[str]:
        """
        Ask the LLM to vote on the best URL for *query*.
        Returns the chosen URL string or None on failure.
        """
        if not self._llm_available or not urls:
            return urls[0] if urls else None

        resp = self._llm.decide_best_url(urls, query)
        if resp.success:
            choice = resp.data.get("response", "").strip()
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(urls):
                    return urls[idx]
            except ValueError:
                pass
        return urls[0]
