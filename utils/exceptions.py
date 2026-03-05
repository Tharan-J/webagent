"""
exceptions.py
Custom exception hierarchy for the web-automation agent.
"""


class AgentBaseError(Exception):
    """Root exception — catch this to handle any agent error."""


class NavigationError(AgentBaseError):
    """Raised when a page cannot be loaded or navigated to."""


class CaptchaEncounteredError(AgentBaseError):
    """Raised when a CAPTCHA wall is detected on the current page."""


class ExtractionError(AgentBaseError):
    """Raised when content cannot be extracted from a page."""


class SearchEngineExhaustedError(AgentBaseError):
    """Raised when all configured search engines are unavailable."""


class LLMError(AgentBaseError):
    """Raised on an unrecoverable LLM/API call failure."""


class BrowserInitError(AgentBaseError):
    """Raised when the Playwright browser cannot be initialised."""
