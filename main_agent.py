"""
main_agent.py
The orchestrating agent.  Handles:
  1. Intent parsing (stripping filler phrases)
  2. Search-engine selection with CAPTCHA-triggered fallback
  3. SERP link analysis and intelligent result clicking
  4. Content extraction + LLM summarisation
  5. Returning a complete ExecutionSummary
"""

from __future__ import annotations

import time
import urllib.parse
from typing import Any, Dict, List, Optional

from config.agent_config import (
    HEADLESS,
    SEARCH_ENGINES,
    MAX_SEARCH_RESULTS_TO_TRY,
)
from models.data_models import ActionResponse, ExecutionSummary, PageContent
from tools.browser_tool import BrowserTool
from tools.logging_tool import get_logger
from agents.navigation_agent import NavigationAgent
from agents.captcha_agent import CaptchaAgent
from agents.search_results_agent import SearchResultsAgent
from agents.content_extraction_agent import ContentExtractionAgent
from agents.reasoning_agent import ReasoningAgent
from utils.helpers import is_junk_href, strip_filler_phrases, get_domain
from utils.exceptions import (
    CaptchaEncounteredError,
    SearchEngineExhaustedError,
    NavigationError,
)

logger = get_logger(__name__)

# Search-engine result page signals — if the loaded page still looks like
# a SERP we consider the click as having failed.
_SERP_URL_SIGNALS = ["google.com/search", "bing.com/search", "duckduckgo.com/?q"]


class MainAgent:
    """
    Orchestrator: parses the user query, drives search-engine navigation,
    analyses the SERP, clicks through to the best result, and extracts
    + summarises the target page content.
    """

    def __init__(self, headless: bool = HEADLESS) -> None:
        self.headless = headless
        self._all_actions: List[str] = []

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self, query: str, max_steps: int = 20) -> ExecutionSummary:
        """
        Execute the full search-and-extract pipeline for *query*.

        Parameters
        ----------
        query:
            Natural-language user query (e.g. "tell me about Sundar Pichai").
        max_steps:
            Safety cap on the total number of discrete actions.

        Returns
        -------
        A fully populated :class:`~models.data_models.ExecutionSummary`.
        """
        summary = ExecutionSummary(query=query)
        search_term = self._extract_search_term(query)
        logger.info("Clean search term: '%s'", search_term)
        self._log("Query parsed — search term: " + search_term)

        with BrowserTool(headless=self.headless) as browser:
            nav_agent = NavigationAgent(browser)
            captcha_agent = CaptchaAgent(browser)
            serp_agent = SearchResultsAgent(browser)
            extraction_agent = ContentExtractionAgent(browser)
            reasoning_agent = ReasoningAgent(browser)

            # ----------------------------------------------------------
            # 1.  Try each search engine in turn
            # ----------------------------------------------------------
            serp_data: Optional[Dict] = None
            engine_used: str = ""

            for engine in SEARCH_ENGINES:
                if len(self._all_actions) >= max_steps:
                    break

                engine_name = engine["name"]
                self._log(f"Trying search engine: {engine_name}")

                nav_result = self._navigate_to_search_engine(
                    browser, engine, search_term
                )
                if not nav_result.success:
                    self._log(f"{engine_name} navigation failed — next engine")
                    continue

                # Check for CAPTCHA immediately after loading the SERP
                captcha_resp = captcha_agent.run()
                self._merge_actions(captcha_agent)

                if not captcha_resp.success:
                    summary.captcha_encountered = True
                    summary.fallbacks_used += 1
                    self._log(f"CAPTCHA on {engine_name} — falling back")
                    continue

                # ----------------------------------------------------------
                # 2.  Analyse the SERP
                # ----------------------------------------------------------
                se_domain = get_domain(browser.get_current_url())
                serp_resp = self._analyse_search_page(serp_agent, se_domain)
                self._merge_actions(serp_agent)

                if not serp_resp.success:
                    self._log(f"SERP analysis failed on {engine_name}")
                    continue

                serp_data = serp_resp.data
                engine_used = engine_name
                break  # Got usable SERP data — proceed

            if serp_data is None:
                summary.status = "failed"
                summary.error_message = "All search engines failed or returned CAPTCHAs."
                summary.actions_taken = list(self._all_actions)
                return summary

            summary.search_engine_used = engine_used

            # ----------------------------------------------------------
            # 3.  Click through to a result
            # ----------------------------------------------------------
            main_results: List[Dict] = serp_data.get("main_results", [])
            self._log(f"Candidates to try: {len(main_results)}")

            # Optionally ask the LLM to rank URLs (uses first N to keep token usage low)
            candidate_urls = [r["href"] for r in main_results[:MAX_SEARCH_RESULTS_TO_TRY]]
            best_url = reasoning_agent.pick_best_url(candidate_urls, search_term)
            if best_url and best_url in candidate_urls:
                # Reorder: put LLM pick first
                candidate_urls = [best_url] + [u for u in candidate_urls if u != best_url]
                self._log(f"LLM preferred URL: {best_url}")

            page_content: Optional[PageContent] = None

            for href in candidate_urls:
                if len(self._all_actions) >= max_steps:
                    break
                if is_junk_href(href):
                    continue

                self._log(f"Attempting result: {href}")
                click_result = browser.navigate(href)
                self._log(f"Navigated → {browser.get_current_url()}")

                if not click_result.success:
                    continue

                new_url = browser.get_current_url()

                # Verify we actually left the SERP
                if self._still_on_serp(new_url):
                    self._log("Still on SERP after click — trying next result")
                    continue

                # Check for CAPTCHA on target page
                captcha_resp2 = captcha_agent.run()
                if not captcha_resp2.success:
                    summary.captcha_encountered = True
                    self._log("CAPTCHA on target page — skipping")
                    continue

                # Extract content
                summary.final_url = new_url
                extract_resp = extraction_agent.run(query=search_term)
                self._merge_actions(extraction_agent)

                if extract_resp.success:
                    page_content = extract_resp.data["page_content"]
                    self._log("Content extracted successfully")
                    break

            # ----------------------------------------------------------
            # 4.  Finalise summary
            # ----------------------------------------------------------
            if page_content is not None:
                summary.page_content = page_content
                summary.status = "success"
            else:
                summary.status = "partial"
                summary.error_message = "Could not extract content from any result."

        summary.actions_taken = list(self._all_actions)
        return summary

    # ------------------------------------------------------------------
    # Intent parsing
    # ------------------------------------------------------------------

    def _extract_search_term(self, query: str) -> str:
        """
        Strip common natural-language filler prefixes so we can build a
        clean search-engine query string.

        Examples
        --------
        "search for Sundar Pichai"   →  "Sundar Pichai"
        "tell me about black holes"  →  "black holes"
        "who is Elon Musk"           →  "Elon Musk"
        """
        return strip_filler_phrases(query)

    # ------------------------------------------------------------------
    # Search-engine navigation
    # ------------------------------------------------------------------

    def _navigate_to_search_engine(
        self,
        browser: BrowserTool,
        engine: Dict,
        search_term: str,
    ) -> ActionResponse:
        """
        Build the search URL for *engine* and navigate to it.

        Returns ActionResponse.  On CAPTCHA the caller is responsible for
        triggering a fallback.
        """
        encoded = urllib.parse.quote_plus(search_term)
        search_url = engine["search_url"].format(query=encoded)
        self._log(f"Searching {engine['name']}: {search_url}")

        nav_resp = browser.navigate(search_url, wait_until="domcontentloaded")
        if nav_resp.success:
            # Brief pause to let JS-rendered results settle
            time.sleep(1.5)
        return nav_resp

    # ------------------------------------------------------------------
    # SERP analysis
    # ------------------------------------------------------------------

    def _analyse_search_page(
        self,
        serp_agent: SearchResultsAgent,
        se_domain: str,
    ) -> ActionResponse:
        """
        Run the SERP agent and return categorised links.

        The result data contains:
            ``main_results``   – external content links (ranked)
            ``internal_links`` – search-engine own links
            ``other_links``    – everything else
        """
        return serp_agent.run(search_engine_domain=se_domain)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _still_on_serp(url: str) -> bool:
        """Return True if *url* looks like a search-results page."""
        low = url.lower()
        return any(signal in low for signal in _SERP_URL_SIGNALS)

    def _log(self, msg: str) -> None:
        logger.info("[MainAgent] %s", msg)
        self._all_actions.append(msg)

    def _merge_actions(self, agent: Any) -> None:
        """Pull action log entries from a sub-agent into our master log."""
        if hasattr(agent, "get_action_log"):
            self._all_actions.extend(agent.get_action_log())
