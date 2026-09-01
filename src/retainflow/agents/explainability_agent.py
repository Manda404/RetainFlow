"""Agent that exposes SHAP explanations in business language."""

from __future__ import annotations

from retainflow.agents.base import AgentResponse
from retainflow.config import ChurnModelConfig
from retainflow.tools.explainability_tool import ExplainabilityTool


class ExplainabilityAgent:
    """Summarize global and future local SHAP explanations for RetainFlow."""

    def __init__(
        self,
        config: ChurnModelConfig,
        explainability_tool: ExplainabilityTool | None = None,
    ) -> None:
        self.config = config
        self.explainability_tool = explainability_tool or ExplainabilityTool(config)

    def global_drivers(self, top_n: int = 5) -> AgentResponse:
        """Return top global churn drivers from the SHAP training artifact."""
        summary = self.explainability_tool.global_shap_summary(top_n=top_n)
        drivers = self.explainability_tool.top_business_drivers(top_n=top_n)
        answer = "Top global model drivers: " + "; ".join(drivers)
        if not drivers:
            answer = "No global SHAP artifact is available yet."
        return AgentResponse(
            agent_name="ExplainabilityAgent",
            answer=answer,
            data=summary,
            metadata={"artifact": str(self.config.shap_summary_path), "top_n": top_n},
        )
