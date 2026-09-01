"""Agent for human-reviewable retention email drafts."""

from __future__ import annotations

import pandas as pd

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
                answer="Aucune recommandation disponible pour rediger un brouillon.",
            )
        draft = self.email_tool.draft_from_recommendation(recommendations.iloc[0])
        return AgentResponse(
            agent_name="EmailDraftingAgent",
            answer="Brouillon genere. Validation humaine obligatoire avant envoi.",
            data=draft,
            metadata={"channel": draft.channel, "requires_human_approval": True},
        )
