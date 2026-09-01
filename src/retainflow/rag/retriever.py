"""TF-IDF retrieval for local RetainFlow strategy documents."""

from __future__ import annotations

import unicodedata
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


@dataclass(frozen=True)
class CorrectiveRetrievalResult:
    """Corrective RAG output with retrieval diagnostics."""

    results: list[RetrievalResult]
    original_query: str
    corrected_query: str
    corrected: bool
    status: str
    min_relevance_score: float


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
        min_relevance_score: float = 0.08,
    ) -> None:
        self.docs_dir = Path(docs_dir)
        self.loader = loader or StrategyDocumentLoader(self.docs_dir)
        self.min_relevance_score = min_relevance_score

    def search(self, query: str, top_k: int = 5) -> list[RetrievalResult]:
        """Return ranked strategy documents for a query."""
        return self._rank(query, top_k=top_k)

    def corrective_search(self, query: str, top_k: int = 5) -> CorrectiveRetrievalResult:
        """Run retrieval, grade relevance, then retry with an enriched query when needed."""
        first_results = self._rank(query, top_k=top_k)
        if self._has_relevant_results(first_results):
            return CorrectiveRetrievalResult(
                results=first_results,
                original_query=query,
                corrected_query=query,
                corrected=False,
                status="relevant",
                min_relevance_score=self.min_relevance_score,
            )

        corrected_query = self._correct_query(query)
        corrected_results = self._rank(corrected_query, top_k=top_k)
        if self._has_relevant_results(corrected_results):
            return CorrectiveRetrievalResult(
                results=corrected_results,
                original_query=query,
                corrected_query=corrected_query,
                corrected=True,
                status="corrected",
                min_relevance_score=self.min_relevance_score,
            )

        best_results = corrected_results or first_results
        return CorrectiveRetrievalResult(
            results=best_results,
            original_query=query,
            corrected_query=corrected_query,
            corrected=corrected_query != query,
            status="low_confidence" if best_results else "no_match",
            min_relevance_score=self.min_relevance_score,
        )

    def _rank(self, query: str, top_k: int = 5) -> list[RetrievalResult]:
        """Return ranked strategy documents for a query without corrective retry."""
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

    def _has_relevant_results(self, results: list[RetrievalResult]) -> bool:
        """Return True when at least one retrieved document clears the relevance threshold."""
        return bool(results and results[0].score >= self.min_relevance_score)

    def _correct_query(self, query: str) -> str:
        """Enrich a weak query with RetainFlow insurance-retention vocabulary."""
        normalized = self._normalize(query)
        expansions: list[str] = []
        keyword_groups = {
            ("prix", "tarif", "prime", "augmentation", "cher", "devis", "concurrent", "price"):
                "sensibilite prix hausse prime remise fidelite devis concurrent ajustement garanties",
            ("paiement", "retard", "rejet", "impaye", "budget", "payment"):
                "incidents paiement rejet prelevement retard regularisation mensualisation fragilite financiere",
            ("service", "reclamation", "plainte", "sla", "insatisfait", "satisfaction", "complaint"):
                "insatisfaction service reclamation dossier non resolu delai traitement geste commercial",
            ("renouvellement", "echeance", "expiration", "renewal"):
                "renouvellement proche echeance contrat appel proactif ajustement garanties retention",
            ("digital", "email", "mobile", "connexion", "engagement", "reengagement"):
                "reengagement digital email espace client notification mobile adoption digitale",
            ("sinistre", "claim", "accident", "indemnisation", "expertise"):
                "sinistre recent indemnisation delai expertise accompagnement conseiller suivi dossier",
            ("valeur", "premium", "high value", "vip", "rentable"):
                "client haute valeur valeur annuelle sauvegardee retention prioritaire conseiller senior",
        }
        for keywords, expansion in keyword_groups.items():
            if any(keyword in normalized for keyword in keywords):
                expansions.append(expansion)

        generic_context = (
            "strategie retention assurance churn client risque action recommandee canal conseiller"
        )
        if not expansions:
            expansions.append(generic_context)
        return " ".join([query, *expansions, generic_context]).strip()

    @staticmethod
    def _normalize(text: str) -> str:
        """Lowercase and remove accents for stable keyword detection."""
        normalized = unicodedata.normalize("NFKD", text.lower())
        return "".join(character for character in normalized if not unicodedata.combining(character))

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
