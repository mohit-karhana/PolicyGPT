"""LLM provider behind a small, replaceable interface.

The application only depends on the `LLMProvider` protocol. The default
implementation speaks the OpenAI-compatible chat-completions HTTP API, which
many providers expose (OpenAI, Azure, Groq, Together, local Ollama, ...), so
"switching providers" is usually just changing LLM_BASE_URL and LLM_MODEL.
A totally different provider (e.g. Anthropic) is one new class implementing
`generate`.

No SDK, no LangChain — one explicit HTTP call, so the request/response
shape stays visible.
"""

import time
from typing import Protocol

import httpx

from app.core.config import settings
from app.core.exceptions import LLMUnavailableError
from app.core.logging import get_logger

logger = get_logger(__name__)


class LLMProvider(Protocol):
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Return the model's text response for one prompt pair."""
        ...


class OpenAICompatibleProvider:
    def __init__(self, api_key: str, model: str, base_url: str, timeout: float) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        started = time.perf_counter()
        try:
            response = httpx.post(
                f"{self._base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    # 0 = deterministic and factual; we want policy answers,
                    # not creative writing.
                    "temperature": 0,
                },
                timeout=self._timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("LLM request failed: %s", exc)
            raise LLMUnavailableError(
                "The language model is currently unavailable. Try again later."
            ) from exc

        latency_ms = (time.perf_counter() - started) * 1000
        logger.info("LLM request: model=%s latency_ms=%.0f", self._model, latency_ms)
        return response.json()["choices"][0]["message"]["content"]


def get_llm_provider() -> LLMProvider:
    if not settings.llm_api_key or not settings.llm_model:
        raise LLMUnavailableError(
            "No LLM configured. Set LLM_API_KEY and LLM_MODEL in the environment."
        )
    return OpenAICompatibleProvider(
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        base_url=settings.llm_base_url,
        timeout=settings.llm_timeout_seconds,
    )
