"""
helpers.py
General-purpose utility functions shared across the project.
"""

from __future__ import annotations

import re
import time
import unicodedata
from urllib.parse import urlparse, urljoin
from typing import List


# ---------------------------------------------------------------------------
# Text utilities
# ---------------------------------------------------------------------------

def clean_text(text: str) -> str:
    """Normalise unicode, collapse whitespace, strip leading/trailing space."""
    text = unicodedata.normalize("NFKD", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def truncate(text: str, max_chars: int = 500, suffix: str = "…") -> str:
    """Return *text* truncated to *max_chars*, appending *suffix* if cut."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + suffix


def strip_filler_phrases(query: str) -> str:
    """
    Remove common natural-language preambles so we get a clean search term.

    Examples
    --------
    "search for Sundar Pichai"  → "Sundar Pichai"
    "tell me about black holes" → "black holes"
    """
    patterns = [
        r"^(please\s+)?(search\s+(for|about|on)\s+)",
        r"^(find\s+(me\s+)?(information\s+)?(about|on)\s+)",
        r"^(tell\s+me\s+about\s+)",
        r"^(look\s+(up|for)\s+)",
        r"^(what\s+is\s+)",
        r"^(who\s+is\s+)",
        r"^(how\s+to\s+)",
        r"^(give\s+me\s+info\s+(about|on)\s+)",
        r"^(i\s+want\s+to\s+know\s+about\s+)",
    ]
    lower = query.lower()
    for pattern in patterns:
        m = re.match(pattern, lower)
        if m:
            # Preserve original casing after the matched prefix
            return query[m.end():].strip()
    return query.strip()


# ---------------------------------------------------------------------------
# URL utilities
# ---------------------------------------------------------------------------

def is_valid_http_url(url: str) -> bool:
    """Return True if *url* looks like a navigable http(s) URL."""
    try:
        parsed = urlparse(url)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except Exception:
        return False


def is_direct_url(query: str) -> bool:
    """
    Return True if the user's query is itself a bare URL rather than
    a natural-language search phrase.
    """
    # Accept with or without scheme
    bare_domain = re.match(
        r"^(https?://)?(www\.)?[a-zA-Z0-9\-]+\.[a-zA-Z]{2,}(/.*)?$",
        query.strip(),
    )
    return bool(bare_domain) and " " not in query.strip()


def normalise_url(url: str) -> str:
    """Prepend https:// if no scheme is present."""
    if not re.match(r"^https?://", url):
        return "https://" + url
    return url


def resolve_href(base_url: str, href: str) -> str:
    """Resolve a potentially relative *href* against *base_url*."""
    return urljoin(base_url, href)


def get_domain(url: str) -> str:
    """Return the netloc (domain + port) of a URL."""
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def is_junk_href(href: str) -> bool:
    """
    Return True for hrefs that should never be clicked as result links.
    Covers javascript: links, bare anchors, and search-parameter links.
    """
    if not href:
        return True
    h = href.strip().lower()
    return (
        h.startswith("javascript:")
        or h.startswith("#")
        or h.startswith("mailto:")
        or h.startswith("tel:")
        or ("?q=" in h and ("google." in h or "bing." in h or "duckduckgo." in h))
        or ("&q=" in h)
        or h in {"", "/", "//"}
    )


# ---------------------------------------------------------------------------
# Timing helpers
# ---------------------------------------------------------------------------

def retry(func, retries: int = 3, delay: float = 1.0, exceptions=(Exception,)):
    """
    Simple retry wrapper.  Returns the function's return value on success,
    or re-raises the last exception after *retries* attempts.
    """
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            return func()
        except exceptions as exc:
            last_exc = exc
            time.sleep(delay * (attempt + 1))
    raise last_exc  # type: ignore[misc]
