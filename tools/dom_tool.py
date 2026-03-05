"""
dom_tool.py
BeautifulSoup-based DOM utilities: clean HTML, extract text, pull links.
"""

from __future__ import annotations

import re
from typing import List, Dict, Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from config.agent_config import NOISE_TAGS
from models.data_models import ActionResponse
from tools.logging_tool import get_logger
from utils.helpers import clean_text, is_valid_http_url

logger = get_logger(__name__)


class DOMTool:
    """
    Stateless helper that operates on raw HTML strings.

    All methods are static/class methods so they can be used without
    instantiating anything.
    """

    # ------------------------------------------------------------------
    # Parsing & cleaning
    # ------------------------------------------------------------------

    @staticmethod
    def parse(html: str) -> BeautifulSoup:
        """Return a BeautifulSoup tree from *html*."""
        return BeautifulSoup(html, "lxml")

    @classmethod
    def clean_soup(cls, soup: BeautifulSoup) -> BeautifulSoup:
        """
        Remove noise tags (script, style, nav, header, footer, …)
        in-place and return the soup.
        """
        for tag_name in NOISE_TAGS:
            for tag in soup.find_all(tag_name):
                tag.decompose()
        return soup

    @classmethod
    def extract_text(cls, html: str) -> str:
        """
        Parse *html*, strip noise tags, and return clean plain text.
        """
        soup = cls.parse(html)
        cls.clean_soup(soup)

        # Prefer main content containers if present
        main = (
            soup.find("main")
            or soup.find("article")
            or soup.find(id=re.compile(r"content|main|article", re.I))
            or soup.find(class_=re.compile(r"content|main|article", re.I))
            or soup.find("body")
        )
        if main is None:
            main = soup

        text = main.get_text(separator="\n", strip=True)
        return clean_text(text)

    # ------------------------------------------------------------------
    # Link extraction
    # ------------------------------------------------------------------

    @classmethod
    def extract_links(cls, html: str, base_url: str = "") -> List[Dict[str, str]]:
        """
        Return a list of dicts with keys ``text`` and ``href`` for every
        ``<a href>`` tag in *html*.  Relative hrefs are resolved against
        *base_url* when provided.
        """
        soup = cls.parse(html)
        links: List[Dict[str, str]] = []
        seen: set[str] = set()

        for a in soup.find_all("a", href=True):
            href: str = a["href"].strip()
            if base_url:
                href = urljoin(base_url, href)
            if href in seen:
                continue
            seen.add(href)
            links.append(
                {
                    "text": clean_text(a.get_text(strip=True)),
                    "href": href,
                }
            )
        return links

    # ------------------------------------------------------------------
    # Structured extraction
    # ------------------------------------------------------------------

    @classmethod
    def extract_title(cls, html: str) -> str:
        soup = cls.parse(html)
        title_tag = soup.find("title")
        if title_tag:
            return clean_text(title_tag.get_text())
        # Fall back to first <h1>
        h1 = soup.find("h1")
        if h1:
            return clean_text(h1.get_text())
        return ""

    @classmethod
    def extract_meta_description(cls, html: str) -> str:
        soup = cls.parse(html)
        meta = soup.find("meta", attrs={"name": re.compile(r"description", re.I)})
        if meta and meta.get("content"):
            return clean_text(meta["content"])
        return ""

    # ------------------------------------------------------------------
    # ActionResponse wrapper
    # ------------------------------------------------------------------

    @classmethod
    def extract_page_data(cls, html: str, url: str = "") -> ActionResponse:
        """
        Convenience method: extract text, title, and links in one call.
        Returns an ``ActionResponse`` with data keys:
        ``title``, ``text``, ``links``, ``meta_description``.
        """
        if not html.strip():
            return ActionResponse.fail("Empty HTML provided.", action="extract_page_data")

        try:
            title = cls.extract_title(html)
            text = cls.extract_text(html)
            links = cls.extract_links(html, base_url=url)
            meta_desc = cls.extract_meta_description(html)

            logger.info(
                "Extracted %d chars of text, %d links from '%s'",
                len(text), len(links), url or "unknown",
            )
            return ActionResponse.ok(
                {
                    "title": title,
                    "text": text,
                    "links": links,
                    "meta_description": meta_desc,
                    "word_count": len(text.split()),
                },
                action="extract_page_data",
            )
        except Exception as exc:
            logger.error("extract_page_data failed: %s", exc)
            return ActionResponse.fail(str(exc), action="extract_page_data")
