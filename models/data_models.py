"""
data_models.py
Pydantic models used as standardised response/payload containers
across every layer of the agent stack.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Core action envelope
# ---------------------------------------------------------------------------

class ActionResponse(BaseModel):
    """Universal return type for every tool and agent method."""

    success: bool = Field(..., description="Whether the operation succeeded.")
    data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary payload returned by the operation.",
    )
    error: str = Field(
        default="",
        description="Human-readable error message when success=False.",
    )
    action: str = Field(
        default="",
        description="Short label describing what was attempted (e.g. 'navigate').",
    )

    # Convenience constructor for failures ----------------------------------
    @classmethod
    def fail(cls, error: str, action: str = "") -> "ActionResponse":
        return cls(success=False, error=error, action=action)

    # Convenience constructor for successes ---------------------------------
    @classmethod
    def ok(cls, data: Dict[str, Any], action: str = "") -> "ActionResponse":
        return cls(success=True, data=data, action=action)


# ---------------------------------------------------------------------------
# Search result entry
# ---------------------------------------------------------------------------

class SearchResult(BaseModel):
    """One organic result scraped from a search-engine results page."""

    title: str = ""
    url: str = ""
    snippet: str = ""
    rank: int = 0


# ---------------------------------------------------------------------------
# Extracted page content
# ---------------------------------------------------------------------------

class PageContent(BaseModel):
    """Cleaned textual content extracted from a target web page."""

    url: str = ""
    title: str = ""
    raw_text: str = ""
    summary: str = ""           # Filled in by the LLM reasoning agent
    word_count: int = 0
    links: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Full execution summary (returned to the CLI)
# ---------------------------------------------------------------------------

class ExecutionSummary(BaseModel):
    """Top-level result object printed by start.py."""

    status: str = "pending"                         # success | failed | partial
    query: str = ""
    final_url: str = ""
    search_engine_used: str = ""
    actions_taken: List[str] = Field(default_factory=list)
    page_content: Optional[PageContent] = None
    error_message: str = ""
    captcha_encountered: bool = False
    fallbacks_used: int = 0
