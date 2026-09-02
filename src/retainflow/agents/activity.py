"""Utilities for exposing truthful agent execution activity."""

from __future__ import annotations

from typing import Any


def activity_item(
    *,
    id: str,
    agent: str,
    business_label: str,
    status: str,
    summary: str,
    tool: str | None = None,
    details: dict[str, Any] | None = None,
    sources: list[dict[str, Any]] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    """Build one normalized activity item, omitting unknown fields."""
    item: dict[str, Any] = {
        "id": id,
        "agent": agent,
        "business_label": business_label,
        "status": status,
        "summary": summary,
    }
    if tool:
        item["tool"] = tool
    if details:
        item["details"] = details
    if sources:
        item["sources"] = sources
    if error:
        item["error"] = error
    return item


def routing_activity(step_id: str, intent: str, mode: str) -> dict[str, Any]:
    """Create the Supervisor activity entry for a routed request."""
    return activity_item(
        id=step_id,
        agent="SupervisorAgent",
        business_label="Request Routing",
        status="completed",
        summary=f"Request routed to {intent} using {mode}.",
        details={"intent": intent, "routing_mode": mode},
    )
