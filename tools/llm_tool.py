"""
llm_tool.py
Thin wrapper around ``langchain-google-genai`` (Gemini).
Provides convenience methods used by the reasoning and extraction agents.
"""

from __future__ import annotations

from typing import Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from config.agent_config import (
    GOOGLE_API_KEY,
    LLM_MODEL,
    LLM_TEMPERATURE,
    LLM_MAX_TOKENS,
)
from models.data_models import ActionResponse
from tools.logging_tool import get_logger
from utils.exceptions import LLMError

logger = get_logger(__name__)


class LLMTool:
    """
    Stateful wrapper around a Gemini chat model.

    Raises :class:`~utils.exceptions.LLMError` if the API key is missing;
    all other errors are surfaced as :class:`~models.data_models.ActionResponse`
    failures.
    """

    def __init__(
        self,
        model: str = LLM_MODEL,
        temperature: float = LLM_TEMPERATURE,
        max_tokens: int = LLM_MAX_TOKENS,
    ) -> None:
        if not GOOGLE_API_KEY:
            raise LLMError(
                "GOOGLE_API_KEY is not set.  "
                "Add it to your .env file or environment variables."
            )
        self._llm = ChatGoogleGenerativeAI(
            model=model,
            temperature=temperature,
            max_output_tokens=max_tokens,
            google_api_key=GOOGLE_API_KEY,
        )
        logger.info("LLMTool initialised with model: %s", model)

    # ------------------------------------------------------------------
    # Core invocation
    # ------------------------------------------------------------------

    def chat(
        self,
        user_message: str,
        system_message: Optional[str] = None,
    ) -> ActionResponse:
        """
        Send a single-turn message to the LLM.

        Parameters
        ----------
        user_message:
            The human turn content.
        system_message:
            Optional system instruction prepended before the user message.

        Returns
        -------
        ActionResponse with ``data["response"]`` containing the model text.
        """
        messages = []
        if system_message:
            messages.append(SystemMessage(content=system_message))
        messages.append(HumanMessage(content=user_message))

        try:
            response = self._llm.invoke(messages)
            text = response.content
            logger.debug("LLM response (%d chars): %s…", len(text), text[:120])
            return ActionResponse.ok({"response": text}, action="llm_chat")
        except Exception as exc:
            logger.error("LLM call failed: %s", exc)
            return ActionResponse.fail(str(exc), action="llm_chat")

    # ------------------------------------------------------------------
    # Convenience prompts
    # ------------------------------------------------------------------

    def summarise(self, text: str, query: str = "") -> ActionResponse:
        """
        Ask the LLM to summarise *text* (optionally focused on *query*).
        """
        focus = f" Focus on answering: «{query}»." if query else ""
        system = (
            "You are a precise research assistant.  "
            "Summarise the provided web-page content clearly and concisely.  "
            "Use bullet points where helpful.  "
            "Do not add information not present in the source text."
        )
        user = f"Summarise the following content.{focus}\n\n---\n{text}"
        return self.chat(user, system_message=system)

    def extract_facts(self, text: str, query: str) -> ActionResponse:
        """
        Ask the LLM to extract facts from *text* relevant to *query*.
        """
        system = (
            "You are an expert information extractor.  "
            "Extract only the facts directly relevant to the user's question.  "
            "Present them as a numbered list.  "
            "If the text does not contain relevant facts, say so plainly."
        )
        user = f"Question: {query}\n\nSource text:\n---\n{text}"
        return self.chat(user, system_message=system)

    def decide_best_url(self, urls: list[str], query: str) -> ActionResponse:
        """
        Given a list of candidate URLs from a SERP, ask the LLM which
        is most likely to answer *query*.
        """
        numbered = "\n".join(f"{i+1}. {u}" for i, u in enumerate(urls))
        system = (
            "You are a web-search strategist.  "
            "Given the user's query and a list of candidate URLs, "
            "return ONLY the number of the URL most likely to contain the answer.  "
            "Respond with a single digit, nothing else."
        )
        user = f"Query: {query}\n\nURLs:\n{numbered}"
        return self.chat(user, system_message=system)
