"""RAG agent for targeted marketing and retention strategy documents."""

from __future__ import annotations

import os
from pathlib import Path

from retainflow.agents.base import AgentResponse
from retainflow.tools.rag_tool import StrategyRAGTool


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
            )

        matches = self.rag_tool.search(question, top_k=limit)
        if matches.empty:
            answer = "Aucune strategie marketing ciblee trouvee pour cette question."
        else:
            titles = ", ".join(matches["title"].head(3).tolist())
            answer = f"{len(matches)} strategies marketing ciblees trouvees: {titles}."
        return AgentResponse(
            agent_name="StrategyRAGAgent",
            answer=answer,
            data=matches,
            metadata={"docs_dir": str(self.docs_dir), "top_k": limit},
        )
