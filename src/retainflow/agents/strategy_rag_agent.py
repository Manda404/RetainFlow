"""RAG agent for targeted marketing and retention strategy documents."""

from __future__ import annotations

import os
from pathlib import Path

from retainflow.agents.activity import activity_item
from retainflow.agents.base import AgentResponse
from retainflow.tools.rag_tool import StrategyRAGTool

TITLE_TRANSLATIONS = {
    "Strategie Retention - Clients Sensibles Au Prix": "Retention Strategy - Price-Sensitive Customers",
    "Strategie Retention - Insatisfaction Service": "Retention Strategy - Service Dissatisfaction",
    "Strategie Retention - Incidents De Paiement": "Retention Strategy - Payment Incidents",
    "Strategie Retention - Renouvellement Proche": "Retention Strategy - Upcoming Renewal",
    "Strategie Retention - Reengagement Digital": "Retention Strategy - Digital Re-Engagement",
    "Strategie Retention - Sinistre Recent": "Retention Strategy - Recent Claim",
    "Strategie Retention - Client Haute Valeur": "Retention Strategy - High-Value Customer",
}


class StrategyRAGAgent:
    """Retrieve targeted marketing strategies from the local RAG corpus."""

    def __init__(
        self,
        docs_dir: str | Path | None = None,
        rag_tool: StrategyRAGTool | None = None,
    ) -> None:
        configured_docs_dir = docs_dir or os.getenv(
            "RETAINFLOW_RAG_DOCS_DIR", "data/docs/strategy_marketing"
        )
        self.docs_dir = Path(configured_docs_dir)
        self.rag_tool = rag_tool or StrategyRAGTool(self.docs_dir)

    def search(self, question: str, limit: int = 5) -> AgentResponse:
        """Return ranked strategy documents for a business question."""
        if not self.docs_dir.exists():
            return AgentResponse(
                agent_name="StrategyRAGAgent",
                answer=f"Dossier documentaire introuvable: {self.docs_dir}",
                data=[],
                metadata={
                    "activity": [
                        activity_item(
                            id="step_1",
                            agent="StrategyRAGAgent",
                            tool="StrategyRAGTool",
                            business_label="Retention Knowledge",
                            status="failed",
                            summary="Retention strategy document folder was not found.",
                            error=f"Document folder not found: {self.docs_dir}",
                        )
                    ]
                },
                business_type="retention_strategy",
            )

        matches, retrieval_metadata = self.rag_tool.corrective_search(question, top_k=limit)
        if matches.empty:
            answer = "No targeted marketing strategy was found for this question."
        else:
            matches = matches.copy()
            matches["title"] = matches["title"].map(lambda title: TITLE_TRANSLATIONS.get(title, title))
            titles = ", ".join(matches["title"].head(3).tolist())
            if retrieval_metadata["corrected"]:
                answer = (
                    f"Corrective RAG enriched the query and found {len(matches)} targeted "
                    f"marketing strategies: {titles}."
                )
            else:
                answer = f"{len(matches)} targeted marketing strategies found: {titles}."
        return AgentResponse(
            agent_name="StrategyRAGAgent",
            answer=answer,
            data=matches,
            metadata={
                "docs_dir": str(self.docs_dir),
                "top_k": limit,
                **retrieval_metadata,
                "activity": [
                    activity_item(
                        id="step_1",
                        agent="StrategyRAGAgent",
                        tool="StrategyRAGTool",
                        business_label="Retention Knowledge",
                        status="completed",
                        summary=f"Retrieved {len(matches)} retention strategy documents.",
                        details={
                            "documents": len(matches),
                            "retrieval_status": retrieval_metadata.get("retrieval_status"),
                            "corrected": retrieval_metadata.get("corrected"),
                        },
                        sources=matches[["document_id", "title", "path", "score"]].to_dict(
                            orient="records"
                        )
                        if not matches.empty
                        else None,
                    )
                ],
            },
            business_type="retention_strategy",
        )
