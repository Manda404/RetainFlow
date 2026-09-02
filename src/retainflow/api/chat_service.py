"""Service functions that connect FastAPI endpoints to RetainFlow agents."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import pandas as pd
from plotly.graph_objects import Figure

from retainflow.agents import StrategyRAGAgent, SupervisorAgent
from retainflow.agents.activity import activity_item
from retainflow.agents.base import AgentResponse
from retainflow.config import ChurnModelConfig
from retainflow.tools.sql_tool import SQLTool


class AgentAPIService:
    """Small application service wrapping RetainFlow agents for HTTP usage."""

    def __init__(self, config: ChurnModelConfig) -> None:
        self.config = config
        self.supervisor = SupervisorAgent(config)
        self.rag_agent = StrategyRAGAgent()
        self.sql_tool = SQLTool(config)

    def chat(self, message: str, limit: int = 5) -> dict[str, Any]:
        """Run the supervisor and serialize its response for the frontend."""
        response = self.supervisor.answer(message, limit=limit)
        return serialize_agent_response(response)

    def customer_profile(self, customer_id: str) -> dict[str, Any]:
        """Return the current profile view for a single customer."""
        response = self.supervisor.customer_profile_agent.by_customer_id(customer_id)
        return serialize_agent_response(response)

    def rag_search(self, query: str, top_k: int = 5) -> dict[str, Any]:
        """Search the targeted marketing RAG corpus."""
        response = self.rag_agent.search(query, limit=top_k)
        return serialize_agent_response(response)

    def sql_query(self, sql: str, limit: int = 100) -> dict[str, Any]:
        """Execute an explicit read-only SQL query."""
        result = self.sql_tool.query(sql, limit=limit)
        response = AgentResponse(
            agent_name="SQLTool",
            answer=f"Query executed with {result.row_count} returned rows.",
            data=result.dataframe,
            metadata={
                "sql": result.sql,
                "row_count": result.row_count,
                "truncated": result.truncated,
                "activity": [
                    activity_item(
                        id="step_1",
                        agent="SQLTool",
                        tool="SQLTool",
                        business_label="Customer Data",
                        status="completed",
                        summary=f"Executed read-only SQL and returned {result.row_count} rows.",
                        details={
                            "rows": result.row_count,
                            "truncated": result.truncated,
                            "sql": result.sql,
                        },
                    )
                ],
            },
            business_type="data_table",
        )
        return serialize_agent_response(response)


def serialize_agent_response(response: AgentResponse) -> dict[str, Any]:
    """Convert an AgentResponse to a JSON-ready API payload."""
    payload: dict[str, Any] = {
        "agent_name": response.agent_name,
        "answer": response.answer,
        "response_type": "text",
        "business_type": response.business_type,
        "data": None,
        "figure": None,
        "metadata": _json_ready(response.metadata),
    }

    if isinstance(response.data, pd.DataFrame):
        payload["response_type"] = "table"
        payload["data"] = _dataframe_records(response.data)
        return payload

    if isinstance(response.data, Figure):
        payload["response_type"] = "plotly"
        payload["figure"] = response.data.to_plotly_json()
        return _json_ready(payload)

    if is_dataclass(response.data):
        payload["response_type"] = "email_draft"
        payload["data"] = asdict(response.data)
        return _json_ready(payload)

    if isinstance(response.data, list | dict):
        payload["response_type"] = "records"
        payload["data"] = response.data
        return _json_ready(payload)

    payload["data"] = response.data
    return _json_ready(payload)


def _dataframe_records(dataframe: pd.DataFrame) -> list[dict[str, Any]]:
    """Serialize DataFrame rows while preserving readable dates and decimals."""
    return [_json_ready(row) for row in dataframe.to_dict(orient="records")]


def _json_ready(value: Any) -> Any:
    """Recursively convert common Python objects to JSON-compatible values."""
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "tolist"):
        return _json_ready(value.tolist())
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        try:
            return _json_ready(value.item())
        except ValueError:
            return _json_ready(value.tolist()) if hasattr(value, "tolist") else str(value)
    return value
