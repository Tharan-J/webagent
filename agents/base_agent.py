"""
base_agent.py
Abstract base class that all sub-agents inherit from.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List

from models.data_models import ActionResponse
from tools.browser_tool import BrowserTool
from tools.dom_tool import DOMTool
from tools.interaction_tool import InteractionTool
from tools.logging_tool import get_logger


class BaseAgent(ABC):
    """
    Shared scaffolding for every agent.

    All concrete sub-agents receive the shared :class:`BrowserTool` instance
    so they can cooperate on the same Playwright page without reopening
    the browser.
    """

    def __init__(self, browser: BrowserTool) -> None:
        self.browser = browser
        self.dom = DOMTool()
        self.interaction = InteractionTool(browser)
        self.logger = get_logger(self.__class__.__name__)
        self._action_log: List[str] = []

    # ------------------------------------------------------------------
    # Action logging (contributes to the ExecutionSummary)
    # ------------------------------------------------------------------

    def _log_action(self, action: str) -> None:
        """Record a human-readable action string."""
        self.logger.info("[ACTION] %s", action)
        self._action_log.append(action)

    def get_action_log(self) -> List[str]:
        return list(self._action_log)

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    def run(self, **kwargs: Any) -> ActionResponse:
        """Execute the agent's primary task.  Must be implemented."""
        ...
