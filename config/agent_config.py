"""
agent_config.py
Central configuration for the web automation agent.
All tuneable constants live here — import from this module everywhere else.
"""

from __future__ import annotations
import os
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Browser / Playwright
# ---------------------------------------------------------------------------

HEADLESS: bool = False                  # Overridden via CLI --headless flag
BROWSER_TIMEOUT_MS: int = 30_000       # Default navigation timeout (ms)
SHORT_TIMEOUT_MS: int = 5_000          # For quick element checks
SLOW_MO_MS: int = 80                   # Slow-motion delay between actions (ms)
VIEWPORT: dict = {"width": 1366, "height": 768}

USER_AGENT: str = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# Extra Chromium launch flags for stealth
CHROMIUM_ARGS: list[str] = [
    "--disable-blink-features=AutomationControlled",
    "--disable-features=VizDisplayCompositor",
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--disable-infobars",
    "--disable-extensions",
    "--ignore-certificate-errors",
    "--allow-running-insecure-content",
    "--disable-web-security",
    "--lang=en-US,en;q=0.9",
    "--window-size=1366,768",
    "--start-maximized",
]

# ---------------------------------------------------------------------------
# Search Engines  (tried in order; fall back on CAPTCHA or error)
# ---------------------------------------------------------------------------

SEARCH_ENGINES: list[dict] = [
    {
        "name": "Google",
        "search_url": "https://www.google.com/search?q={query}&hl=en",
        "result_selector": "div#search a[href]",
    },
    {
        "name": "DuckDuckGo",
        "search_url": "https://duckduckgo.com/?q={query}&kl=us-en",
        "result_selector": "a[data-testid='result-title-a']",
    },
    {
        "name": "Bing",
        "search_url": "https://www.bing.com/search?q={query}&cc=en",
        "result_selector": "li.b_algo h2 a",
    },
]

# ---------------------------------------------------------------------------
# LLM (Google Gemini via langchain-google-genai)
# ---------------------------------------------------------------------------

GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
LLM_MODEL: str = "gemini-2.5-flash-lite"
LLM_TEMPERATURE: float = 0.2
LLM_MAX_TOKENS: int = 2048

# ---------------------------------------------------------------------------
# Scraping & extraction
# ---------------------------------------------------------------------------

MAX_SEARCH_RESULTS_TO_TRY: int = 5      # How many SERP links to attempt
CONTENT_PREVIEW_CHARS: int = 1_500      # Characters shown in CLI preview
MAX_PAGE_TEXT_CHARS: int = 12_000       # Chars sent to LLM for summarisation

# Tags stripped before text extraction
NOISE_TAGS: list[str] = [
    "script", "style", "nav", "header", "footer",
    "aside", "form", "noscript", "svg", "iframe",
]

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE: str = "agent_run.log"
