"""TF-IDF retrieval for local RetainFlow strategy documents."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from retainflow.rag.document_loader import StrategyDocument, StrategyDocumentLoader


@dataclass(frozen=True)
class RetrievalResult:
    """One retrieved strategy document with score and preview."""

    document_id: str
    title: str
    path: Path
    score: float
    preview: str


class StrategyRetriever:
    """Retrieve the most relevant strategy documents for a business question.

    This is a local RAG foundation: no external API key is required. It uses a
    TF-IDF representation, which is enough to make strategy lookup deterministic
    and testable before adding embeddings or a vector database.
    """

    def __init__(
        self,
        docs_dir: str | Path,
        loader: StrategyDocumentLoader | None = None,
    ) -> None:
        self.docs_dir = Path(docs_dir)
        self.loader = loader or StrategyDocumentLoader(self.docs_dir)

    def search(self, query: str, top_k: int = 5) -> list[RetrievalResult]:
        """Return ranked strategy documents for a query."""
        documents = self.loader.load()
        if not documents:
            return []

        corpus = [document.text for document in documents]
        vectorizer = TfidfVectorizer(
            strip_accents="unicode",
            lowercase=True,
            ngram_range=(1, 2),
            stop_words=self._french_stop_words(),
        )
        document_matrix = vectorizer.fit_transform(corpus)
        query_vector = vectorizer.transform([query])
        scores = cosine_similarity(query_vector, document_matrix).ravel()

        ranked = sorted(
            zip(documents, scores, strict=True),
            key=lambda item: float(item[1]),
            reverse=True,
        )
        return [
            RetrievalResult(
                document_id=document.document_id,
                title=document.title,
                path=document.path,
                score=round(float(score), 4),
                preview=self._preview(document),
            )
            for document, score in ranked[:top_k]
            if score > 0
        ]

    @staticmethod
    def _preview(document: StrategyDocument, max_chars: int = 700) -> str:
        """Return a compact text preview for the agent response."""
        compact = " ".join(document.text.split())
        return compact[:max_chars]

    @staticmethod
    def _french_stop_words() -> list[str]:
        """Small French stop-word list to keep retrieval focused on business terms."""
        return [
            "a",
            "au",
            "aux",
            "avec",
            "ce",
            "ces",
            "dans",
            "de",
            "des",
            "du",
            "elle",
            "en",
            "et",
            "il",
            "la",
            "le",
            "les",
            "leur",
            "pour",
            "que",
            "qui",
            "sur",
            "un",
            "une",
        ]
