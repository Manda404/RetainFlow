"""Document loading for RetainFlow strategy RAG."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StrategyDocument:
    """A local strategy document loaded from Markdown or text files."""

    document_id: str
    title: str
    path: Path
    text: str


class StrategyDocumentLoader:
    """Load marketing and retention strategy documents from a local folder."""

    def __init__(self, docs_dir: str | Path) -> None:
        self.docs_dir = Path(docs_dir)

    def load(self) -> list[StrategyDocument]:
        """Return every Markdown and text document found in the strategy folder."""
        if not self.docs_dir.exists():
            return []

        documents: list[StrategyDocument] = []
        for path in sorted(self.docs_dir.rglob("*")):
            if path.suffix.lower() not in {".md", ".txt"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore").strip()
            if not text:
                continue
            documents.append(
                StrategyDocument(
                    document_id=path.stem,
                    title=self._title_from_text(text, fallback=path.stem),
                    path=path,
                    text=text,
                )
            )
        return documents

    @staticmethod
    def _title_from_text(text: str, fallback: str) -> str:
        """Use the first Markdown heading as title when it exists."""
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                return stripped.lstrip("#").strip()
        return fallback.replace("_", " ").title()
