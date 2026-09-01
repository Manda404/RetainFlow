"""Tool exposing local strategy RAG retrieval to agents."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from retainflow.rag import StrategyRetriever


class StrategyRAGTool:
    """Search targeted marketing strategy documents and return a DataFrame."""

    def __init__(self, docs_dir: str | Path = "data/docs/strategy_marketing") -> None:
        self.docs_dir = Path(docs_dir)
        self.retriever = StrategyRetriever(self.docs_dir)

    def search(self, query: str, top_k: int = 5) -> pd.DataFrame:
        """Return relevant strategy documents as a table usable by agents."""
        results = self.retriever.search(query, top_k=top_k)
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
