"""Agent dedicated to KPI analysis."""

from __future__ import annotations

from retainflow.agents.activity import activity_item
from retainflow.agents.base import AgentResponse
from retainflow.config import ChurnModelConfig
from retainflow.tools.kpi_tool import KPITool


class KPIAgent:
    """Choose and compute RetainFlow KPIs from a business question."""

    def __init__(self, config: ChurnModelConfig, kpi_tool: KPITool | None = None) -> None:
        self.config = config
        self.kpi_tool = kpi_tool or KPITool(config)

    def answer(self, question: str) -> AgentResponse:
        """Return a KPI table and a short interpretation."""
        lowered = question.lower()
        if "split" in lowered or "churn rate" in lowered or "taux de churn" in lowered:
            result = self.kpi_tool.churn_rate_by_split()
            label = "churn rate by split"
        elif any(word in lowered for word in ("agence", "agency")) and any(
            word in lowered for word in ("semaine", "week", "weekly")
        ):
            result = self.kpi_tool.weekly_contact_rate_by_agency()
            label = "weekly contacts by agency"
        elif any(word in lowered for word in ("agence", "agency")):
            result = self.kpi_tool.priority_clients_by_agency()
            label = "priority customers by agency"
        elif any(word in lowered for word in ("action", "recommend", "recommand", "distribution")):
            result = self.kpi_tool.recommended_actions_distribution()
            label = "recommended actions distribution"
        else:
            result = self.kpi_tool.priority_clients_by_region()
            label = "priority customers by region"

        return AgentResponse(
            agent_name="KPIAgent",
            answer=f"KPI computed: {label}. {result.row_count} returned rows.",
            data=result.dataframe,
            metadata={
                "sql": result.sql,
                "kpi": label,
                "row_count": result.row_count,
                "activity": [
                    activity_item(
                        id="step_1",
                        agent="KPIAgent",
                        tool="KPITool",
                        business_label="Business KPI",
                        status="completed",
                        summary=f"Computed KPI: {label}.",
                        details={"rows": result.row_count, "kpi": label, "sql": result.sql},
                    )
                ],
            },
            business_type="kpi",
        )
