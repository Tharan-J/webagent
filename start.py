"""
start.py
CLI entry point for the Advanced Web Automation & Scraping Agent.

Usage examples
--------------
# Natural-language query (triggers full search pipeline)
python start.py --query "tell me about Sundar Pichai"

# Direct URL (skips search, loads page directly)
python start.py --query "https://en.wikipedia.org/wiki/Python_(programming_language)"

# Headless mode
python start.py --query "search for black holes" --headless

# Cap the number of internal actions
python start.py --query "latest AI news" --steps 15
"""

from __future__ import annotations

import argparse
import sys
import textwrap

from models.data_models import ExecutionSummary, PageContent
from utils.helpers import is_direct_url
from tools.logging_tool import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Pretty-printer
# ---------------------------------------------------------------------------

_SEP = "─" * 72

def _banner(title: str) -> str:
    return f"\n{_SEP}\n  {title}\n{_SEP}"


def _print_summary(summary: ExecutionSummary) -> None:
    from config.agent_config import CONTENT_PREVIEW_CHARS

    print(_banner("EXECUTION SUMMARY"))
    print(f"  Status          : {summary.status.upper()}")
    print(f"  Query           : {summary.query}")
    print(f"  Search engine   : {summary.search_engine_used or 'N/A (direct URL)'}")
    print(f"  Final URL       : {summary.final_url or 'N/A'}")
    print(f"  CAPTCHA hit     : {summary.captcha_encountered}")
    print(f"  Fallbacks used  : {summary.fallbacks_used}")

    if summary.error_message:
        print(f"  Error           : {summary.error_message}")

    # Actions taken
    print(_banner("ACTIONS TAKEN"))
    for i, action in enumerate(summary.actions_taken, 1):
        print(f"  {i:>3}. {action}")

    # Page content
    if summary.page_content:
        pc: PageContent = summary.page_content
        print(_banner("EXTRACTED CONTENT"))
        print(f"  Title      : {pc.title}")
        print(f"  URL        : {pc.url}")
        print(f"  Word count : {pc.word_count}")

        if pc.summary:
            print("\n  ── LLM Summary ──")
            wrapped = textwrap.fill(pc.summary, width=70, initial_indent="  ",
                                    subsequent_indent="  ")
            print(wrapped)
        else:
            preview = pc.raw_text[:CONTENT_PREVIEW_CHARS]
            print("\n  ── Raw Text Preview ──")
            wrapped = textwrap.fill(preview, width=70, initial_indent="  ",
                                    subsequent_indent="  ")
            print(wrapped)
            if len(pc.raw_text) > CONTENT_PREVIEW_CHARS:
                print(f"\n  … [{len(pc.raw_text) - CONTENT_PREVIEW_CHARS} more chars]")
    else:
        print("\n  No content extracted.")

    print(f"\n{_SEP}\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="start.py",
        description="Advanced Web Automation & Scraping Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """\
            Examples:
              python start.py --query "tell me about Sundar Pichai"
              python start.py --query "https://example.com" --headless
            """
        ),
    )
    parser.add_argument(
        "--query", "-q",
        required=True,
        help="A natural-language query OR a direct URL to scrape.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=False,
        help="Run the browser in headless mode (no visible window).",
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=20,
        help="Maximum number of internal agent steps (default: 20).",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    query: str = args.query.strip()
    headless: bool = args.headless
    max_steps: int = max(1, args.steps)

    logger.info("Starting agent — query: '%s'  headless: %s  steps: %d",
                query, headless, max_steps)

    summary: ExecutionSummary

    if is_direct_url(query):
        # ----------------------------------------------------------------
        # Route A: Direct URL extraction
        # ----------------------------------------------------------------
        from utils.url_handler import URLHandler
        logger.info("Detected direct URL — routing to URLHandler")
        handler = URLHandler(headless=headless)
        summary = handler.handle(url=query, query=query)
    else:
        # ----------------------------------------------------------------
        # Route B: Natural-language query → full search pipeline
        # ----------------------------------------------------------------
        from main_agent import MainAgent
        logger.info("Natural-language query — routing to MainAgent")
        agent = MainAgent(headless=headless)
        summary = agent.run(query=query, max_steps=max_steps)

    _print_summary(summary)

    # Exit with a non-zero code if the run failed
    if summary.status == "failed":
        sys.exit(1)


if __name__ == "__main__":
    main()
