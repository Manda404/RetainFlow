"""Agent for assembling customer-level context before advice or explanation."""

from __future__ import annotations

from retainflow.agents.base import AgentResponse
from retainflow.config import ChurnModelConfig
from retainflow.tools.customer_profile_tool import CustomerProfileTool


class CustomerProfileAgent:
    """Retrieve a customer's 360 profile with prediction and recommendation context."""

    def __init__(
        self,
        config: ChurnModelConfig,
        profile_tool: CustomerProfileTool | None = None,
    ) -> None:
        self.config = config
        self.profile_tool = profile_tool or CustomerProfileTool(config)

    def by_customer_id(self, customer_id: str) -> AgentResponse:
        """Return the latest available profile for one customer."""
        result = self.profile_tool.by_customer_id(customer_id=customer_id)
        if result.dataframe.empty:
            answer = f"Aucun profil trouve pour le client {customer_id}."
        else:
            answer = f"Profil client charge pour {customer_id}: {result.row_count} lignes trouvees."
        return AgentResponse(
            agent_name="CustomerProfileAgent",
            answer=answer,
            data=result.dataframe,
            metadata={"sql": result.sql, "row_count": result.row_count},
        )
