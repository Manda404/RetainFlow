"""Tool exposing local strategy RAG retrieval to agents."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from retainflow.rag import CorrectiveRetrievalResult, StrategyRetriever


class StrategyRAGTool:
    """Search targeted marketing strategy documents and return a DataFrame."""

    def __init__(self, docs_dir: str | Path = "data/docs/strategy_marketing") -> None:
        self.docs_dir = Path(docs_dir)
        self.retriever = StrategyRetriever(self.docs_dir)

    def search(self, query: str, top_k: int = 5) -> pd.DataFrame:
        """Return relevant strategy documents as a table usable by agents."""
        results = self.retriever.search(query, top_k=top_k)
        return self._results_to_frame(results)

    def corrective_search(self, query: str, top_k: int = 5) -> tuple[pd.DataFrame, dict]:
        """Return corrective RAG results and retrieval diagnostics."""
        result = self.retriever.corrective_search(query, top_k=top_k)
        return self._results_to_frame(result.results), self._metadata(result)

    @staticmethod
    def _results_to_frame(results) -> pd.DataFrame:
        """Convert retrieval results to an agent-friendly DataFrame."""
        return pd.DataFrame(
            [
                {
                    "document_id": result.document_id,
                    "title": result.title,
                    "path": str(result.path),
                    "score": result.score,
                    "preview": result.preview,
                }
                for result in results
            ]
        )

    @staticmethod
    def _metadata(result: CorrectiveRetrievalResult) -> dict:
        return {
            "original_query": result.original_query,
            "corrected_query": result.corrected_query,
            "corrected": result.corrected,
            "retrieval_status": result.status,
            "min_relevance_score": result.min_relevance_score,
        }
