"""Agent for human-reviewable retention email drafts."""

from __future__ import annotations

import pandas as pd

from retainflow.agents.activity import activity_item
from retainflow.agents.base import AgentResponse
from retainflow.tools.email_tool import EmailDraftingTool


class EmailDraftingAgent:
    """Draft advisor messages from recommendation rows without sending them."""

    def __init__(self, email_tool: EmailDraftingTool | None = None) -> None:
        self.email_tool = email_tool or EmailDraftingTool()

    def draft_first(self, recommendations: pd.DataFrame) -> AgentResponse:
        """Draft a message for the first recommendation in a DataFrame."""
        if recommendations.empty:
            return AgentResponse(
                agent_name="EmailDraftingAgent",
                answer="No recommendation is available for drafting a message.",
                metadata={
                    "activity": [
                        activity_item(
                            id="step_1",
                            agent="EmailDraftingAgent",
                            tool="EmailDraftingTool",
                            business_label="Email Generation",
                            status="skipped",
                            summary="No recommendation was available for email drafting.",
                            details={"recipients": 0},
                        )
                    ]
                },
                business_type="email_draft",
            )
        draft = self.email_tool.draft_from_recommendation(recommendations.iloc[0])
        return AgentResponse(
            agent_name="EmailDraftingAgent",
            answer="Draft generated. Human approval is required before sending.",
            data=draft,
            metadata={
                "channel": draft.channel,
                "requires_human_approval": True,
                "activity": [
                    activity_item(
                        id="step_1",
                        agent="EmailDraftingAgent",
                        tool="EmailDraftingTool",
                        business_label="Email Generation",
                        status="completed",
                        summary="Generated one retention email draft.",
                        details={"recipients": 1, "channel": draft.channel},
                    )
                ],
            },
            business_type="email_draft",
        )
