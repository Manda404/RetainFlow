"""Optional LLM router for the RetainFlow supervisor."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from retainflow.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class LLMRoute:
    """Routing decision returned by the LLM supervisor layer."""

    intent: str
    reason: str = ""
    confidence: float = 0.0


class LLMRouter:
    """Use a chat model to classify RetainFlow business questions.

    The LLM only decides which controlled workflow should run. It does not
    execute SQL, mutate data, or bypass the deterministic tool guardrails.
    """

    allowed_intents = {
        "retention",
        "kpi",
        "visualization",
        "email",
        "strategy",
        "customer_profile",
        "data_count",
        "data_query",
        "unsupported",
    }

    def __init__(
        self,
        *,
        enabled: bool,
        provider: str,
        model: str,
        api_key: str,
        timeout_seconds: float = 15.0,
        base_url: str | None = None,
    ) -> None:
        self.enabled = enabled
        self.provider = provider.lower().strip()
        self.model = model.strip()
        self.api_key = api_key.strip()
        self.timeout_seconds = timeout_seconds
        self.base_url = (base_url or self._default_base_url(self.provider)).rstrip("/")

    @classmethod
    def from_env(cls) -> LLMRouter:
        """Build a router from environment variables."""
        provider = os.getenv("LLM_PROVIDER", "groq").lower().strip()
        api_key_env = {
            "groq": "GROQ_API_KEY",
            "openai": "OPENAI_API_KEY",
        }.get(provider, "GROQ_API_KEY")
        enabled = os.getenv("RETAINFLOW_LLM_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
        return cls(
            enabled=enabled,
            provider=provider,
            model=os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"),
            api_key=os.getenv(api_key_env, ""),
            timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "15")),
            base_url=os.getenv("LLM_BASE_URL"),
        )

    def route(self, question: str) -> LLMRoute | None:
        """Return a route decision, or None when the LLM is unavailable."""
        if not self.enabled:
            return None
        if not self.api_key:
            logger.warning("LLM routing is enabled but no API key is configured.")
            return None

        try:
            payload = self._chat_payload(question)
            response = self._post_json(f"{self.base_url}/chat/completions", payload)
            content = response["choices"][0]["message"]["content"]
            return self._parse_route(content)
        except (KeyError, IndexError, ValueError, HTTPError, URLError, TimeoutError, OSError) as exc:
            logger.warning("LLM routing failed; falling back to deterministic routing: %s", exc)
            return None

    def _chat_payload(self, question: str) -> dict[str, Any]:
        return {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are the routing supervisor for RetainFlow, an insurance churn "
                        "and retention analytics app. Classify the user question into exactly "
                        "one intent from this list: retention, kpi, visualization, email, "
                        "strategy, customer_profile, data_count, data_query, unsupported. Use data_query "
                        "for safe customer-data exploration that does not ask for churn prediction. Use unsupported when "
                        "the question is outside RetainFlow capabilities or cannot be mapped safely. "
                        "Return only JSON with keys intent, reason, confidence. Do not write SQL."
                    ),
                },
                {"role": "user", "content": question},
            ],
        }

    def _post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        request = Request(
            url,
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310
            return json.loads(response.read().decode("utf-8"))

    def _parse_route(self, content: str) -> LLMRoute | None:
        raw = json.loads(content)
        intent = str(raw.get("intent", "")).strip().lower()
        if intent not in self.allowed_intents:
            raise ValueError(f"Unsupported LLM route intent: {intent}")
        return LLMRoute(
            intent=intent,
            reason=str(raw.get("reason", "")),
            confidence=float(raw.get("confidence", 0.0) or 0.0),
        )

    @staticmethod
    def _default_base_url(provider: str) -> str:
        if provider == "openai":
            return "https://api.openai.com/v1"
        return "https://api.groq.com/openai/v1"
