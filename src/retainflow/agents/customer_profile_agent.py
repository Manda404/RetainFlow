"""Agent for assembling customer-level context before advice or explanation."""

from __future__ import annotations

from retainflow.agents.activity import activity_item
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
            answer = f"No profile found for customer {customer_id}."
        else:
            answer = f"Latest customer profile loaded for {customer_id}."
        business_type = "customer_not_found" if result.dataframe.empty else "customer_profile"
        return AgentResponse(
            agent_name="CustomerProfileAgent",
            answer=answer,
            data=result.dataframe,
            metadata={
                "sql": result.sql,
                "row_count": result.row_count,
                "activity": [
                    activity_item(
                        id="step_1",
                        agent="CustomerProfileAgent",
                        tool="CustomerProfileTool",
                        business_label="Customer Data",
                        status="completed",
                        summary=(
                            f"Customer profile retrieved for {customer_id}."
                            if not result.dataframe.empty
                            else f"Customer {customer_id} was not found."
                        ),
                        details={"rows": result.row_count, "sql": result.sql},
                    )
                ],
            },
            business_type=business_type,
        )
