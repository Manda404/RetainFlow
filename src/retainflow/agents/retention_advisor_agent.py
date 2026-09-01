"""Agent that explains the next best retention actions."""

from __future__ import annotations

from retainflow.agents.base import AgentResponse
from retainflow.config import ChurnModelConfig
from retainflow.tools.retention_tool import RetentionTool


class RetentionAdvisorAgent:
    """Read RetainFlow priority outputs and produce advisor-facing summaries."""

    def __init__(self, config: ChurnModelConfig, retention_tool: RetentionTool | None = None) -> None:
        self.config = config
        self.retention_tool = retention_tool or RetentionTool(config)

    def top_clients(self, limit: int = 5) -> AgentResponse:
        """Return the most urgent customers with business action context."""
        result = self.retention_tool.top_priority_clients(limit=limit)
        return AgentResponse(
            agent_name="RetentionAdvisorAgent",
            answer=f"{result.row_count} priority customers identified for retention action.",
            data=result.dataframe,
            metadata={"sql": result.sql, "row_count": result.row_count},
        )

    def top_recommendations(self, limit: int = 5) -> AgentResponse:
        """Return the top human-reviewable recommendations."""
        result = self.retention_tool.top_recommendations(limit=limit)
        return AgentResponse(
            agent_name="RetentionAdvisorAgent",
            answer=f"{result.row_count} retention recommendations ready for human review.",
            data=result.dataframe,
            metadata={"sql": result.sql, "row_count": result.row_count},
        )
