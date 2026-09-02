"""LLM-backed business explanation writer for RetainFlow."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from retainflow.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class LLMReasoningResult:
    """Final explanation produced by an LLM from controlled evidence."""

    answer: str
    confidence: float
    used_facts: list[str]


class LLMReasoningAgent:
    """Use an LLM to write the final answer from verified reasoning facts."""

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
    def from_env(cls) -> LLMReasoningAgent:
        provider = os.getenv("LLM_PROVIDER", "groq").lower().strip()
        api_key_env = {
            "groq": "GROQ_API_KEY",
            "openai": "OPENAI_API_KEY",
        }.get(provider, "GROQ_API_KEY")
        enabled = os.getenv("RETAINFLOW_LLM_REASONING_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
        return cls(
            enabled=enabled,
            provider=provider,
            model=os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"),
            api_key=os.getenv(api_key_env, ""),
            timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "15")),
            base_url=os.getenv("LLM_BASE_URL"),
        )

    def explain_customer_risk(
        self,
        *,
        question: str,
        customer_id: str,
        deterministic_answer: str,
        reasoning: dict[str, Any],
    ) -> LLMReasoningResult | None:
        """Return an LLM-written answer, or None when unavailable."""
        if not self.enabled:
            return None
        if not self.api_key:
            logger.warning("LLM reasoning is enabled but no API key is configured.")
            return None

        try:
            payload = self._chat_payload(
                question=question,
                customer_id=customer_id,
                deterministic_answer=deterministic_answer,
                reasoning=reasoning,
            )
            response = self._post_json(f"{self.base_url}/chat/completions", payload)
            content = response["choices"][0]["message"]["content"]
            return self._parse_result(content)
        except (KeyError, IndexError, ValueError, HTTPError, URLError, TimeoutError, OSError) as exc:
            logger.warning("LLM reasoning failed; using deterministic explanation: %s", exc)
            return None

    def _chat_payload(
        self,
        *,
        question: str,
        customer_id: str,
        deterministic_answer: str,
        reasoning: dict[str, Any],
    ) -> dict[str, Any]:
        evidence = {
            "customer_id": customer_id,
            "prediction": reasoning.get("prediction"),
            "customer_signals": reasoning.get("signals", []),
            "global_shap_drivers": reasoning.get("shap_drivers", []),
            "recommended_action": reasoning.get("recommended_action"),
            "consistency_note": (reasoning.get("prediction") or {}).get("consistency_note")
            if isinstance(reasoning.get("prediction"), dict)
            else None,
            "fallback_answer": deterministic_answer,
        }
        return {
            "model": self.model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are RetainFlow's customer-risk reasoning agent for insurance retention. "
                        "Write a concise business explanation in French using only the supplied evidence. "
                        "Never say the customer will churn with certainty; speak in probabilities. "
                        "Explain the churn probability, the strongest customer signals, how the global SHAP "
                        "drivers help interpret the model, and the next retention action. "
                        "If there is a consistency note, mention it as a data-quality/calibration point. "
                        "Return only JSON with keys answer, confidence, used_facts."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(_json_ready({"question": question, "evidence": evidence}), ensure_ascii=True),
                },
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

    @staticmethod
    def _parse_result(content: str) -> LLMReasoningResult:
        raw = json.loads(content)
        answer = str(raw.get("answer", "")).strip()
        if not answer:
            raise ValueError("LLM reasoning returned an empty answer.")
        used_facts = raw.get("used_facts", [])
        return LLMReasoningResult(
            answer=answer,
            confidence=float(raw.get("confidence", 0.0) or 0.0),
            used_facts=[str(item) for item in used_facts] if isinstance(used_facts, list) else [],
        )

    @staticmethod
    def _default_base_url(provider: str) -> str:
        if provider == "openai":
            return "https://api.openai.com/v1"
        return "https://api.groq.com/openai/v1"


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "item"):
        try:
            return _json_ready(value.item())
        except ValueError:
            return str(value)
    return value
