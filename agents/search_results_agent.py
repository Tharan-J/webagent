"""
search_results_agent.py
Analyses a search-engine results page (SERP) and categorises links into:
  - main_results  (external content links)
  - internal_links (links belonging to the search engine domain)
  - other_links
"""

from __future__ import annotations

from typing import Any, Dict, List
from urllib.parse import urlparse, unquote

from models.data_models import ActionResponse
from agents.base_agent import BaseAgent
from tools.browser_tool import BrowserTool
from utils.helpers import is_junk_href, get_domain, is_valid_http_url


# Domains we never want to click through to
_BLOCKED_DOMAINS = {
    "google.com", "www.google.com",
    "duckduckgo.com", "www.duckduckgo.com",
    "bing.com", "www.bing.com",
    "yahoo.com", "search.yahoo.com",
    "webcache.googleusercontent.com",
    "translate.google.com",
    "maps.google.com",
    "accounts.google.com",
    "support.google.com",
    "policies.google.com",
}


def _unwrap_google_redirect(href: str) -> str:
    """
    Google wraps result URLs in /url?q=<real_url>&… — unwrap them.
    """
    if "/url?q=" in href:
        try:
            q_part = href.split("/url?q=")[1]
            real = q_part.split("&")[0]
            return unquote(real)
        except Exception:
            pass
    return href


class SearchResultsAgent(BaseAgent):
    """
    Given the current SERP page in the browser, extracts and categorises links.
    """

    def run(self, search_engine_domain: str = "", **kwargs: Any) -> ActionResponse:
        """
        Analyse the current SERP page.

        Parameters
        ----------
        search_engine_domain:
            The domain of the current search engine (e.g. "www.google.com").
            Used to classify internal vs external links.

        Returns
        -------
        ActionResponse with:
            ``data["main_results"]``   – List of dicts {title, href}
            ``data["internal_links"]`` – List of dicts {title, href}
            ``data["other_links"]``    – List of dicts {title, href}
        """
        self._log_action("Analysing SERP links")
        url = self.browser.get_current_url()
        html = self.browser.get_page_source()

        if not html:
            return ActionResponse.fail("Empty page source.", action="analyse_serp")

        all_links = self.dom.extract_links(html, base_url=url)
        se_domain = search_engine_domain or get_domain(url)

        main_results: List[Dict] = []
        internal_links: List[Dict] = []
        other_links: List[Dict] = []

        for link in all_links:
            raw_href: str = link["href"]
            text: str = link.get("text", "")

            # Unwrap Google redirect URLs
            href = _unwrap_google_redirect(raw_href)

            # Skip junk
            if is_junk_href(href):
                continue

            # Must be a valid http(s) URL
            if not is_valid_http_url(href):
                continue

            domain = get_domain(href)

            # Classify
            if domain in _BLOCKED_DOMAINS or (se_domain and se_domain in domain):
                internal_links.append({"title": text, "href": href})
            elif domain:
                main_results.append({"title": text, "href": href})
            else:
                other_links.append({"title": text, "href": href})

        # De-duplicate main_results by href
        seen: set[str] = set()
        deduped: List[Dict] = []
        for r in main_results:
            if r["href"] not in seen:
                seen.add(r["href"])
                deduped.append(r)

        self._log_action(
            f"SERP analysis: {len(deduped)} main results, "
            f"{len(internal_links)} internal, {len(other_links)} other"
        )

        return ActionResponse.ok(
            {
                "main_results": deduped,
                "internal_links": internal_links,
                "other_links": other_links,
            },
            action="analyse_serp",
        )
