"""
captcha_agent.py
Detects and attempts to handle CAPTCHAs.
Primary strategy is detection + signalling; automatic solving is not
attempted (requires paid third-party services).  The agent instead raises
a flag so the orchestrator can fall back to another search engine.
"""

from __future__ import annotations

from typing import Any

from models.data_models import ActionResponse
from agents.base_agent import BaseAgent
from tools.browser_tool import BrowserTool
from utils.exceptions import CaptchaEncounteredError


class CaptchaAgent(BaseAgent):
    """
    Thin agent that wraps :meth:`BrowserTool._is_captcha_present`.
    """

    def run(self, **kwargs: Any) -> ActionResponse:
        """
        Check the current page for a CAPTCHA.

        Returns
        -------
        ActionResponse
            ``success=True, data["captcha"]=False``  → no CAPTCHA found
            ``success=False, error="CAPTCHA detected"``  → CAPTCHA present
        """
        self._log_action("Checking for CAPTCHA")
        captcha_present = self.browser._is_captcha_present()

        if captcha_present:
            self._log_action("CAPTCHA detected — flagging for fallback")
            return ActionResponse.fail("CAPTCHA detected on current page.", action="captcha_check")

        return ActionResponse.ok({"captcha": False}, action="captcha_check")

    def assert_no_captcha(self) -> None:
        """
        Convenience: raises :class:`CaptchaEncounteredError` if a CAPTCHA
        is detected on the current page.
        """
        result = self.run()
        if not result.success:
            raise CaptchaEncounteredError(result.error)
