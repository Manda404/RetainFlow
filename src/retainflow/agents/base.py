"""Shared response objects for RetainFlow agents."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AgentResponse:
    """Common response envelope returned by deterministic local agents."""

    agent_name: str
    answer: str
    data: Any | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
