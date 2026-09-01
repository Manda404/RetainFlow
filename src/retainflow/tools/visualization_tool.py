"""Visualization tool using Plotly Express first, with optional static fallbacks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class VisualizationResult:
    """Structured visualization output returned to agents and notebooks."""

    figure: Any
    chart_type: str
    title: str
    interpretation: str
    output_path: Path | None = None


class VisualizationTool:
    """Generate business charts from SQL or model result DataFrames.

    Plotly Express is the default because the agentic notebook should be able to
    show interactive charts. Seaborn and Matplotlib can be added later for
    statistical diagnostic charts where static output is preferable.
    """

    def __init__(self, default_size: tuple[int, int] = (1100, 520)) -> None:
        self.default_size = default_size

    def bar(
        self,
        dataframe: pd.DataFrame,
        x: str,
        y: str,
        color: str | None = None,
        title: str | None = None,
        path: str | Path | None = None,
    ) -> VisualizationResult:
        """Create a Plotly Express bar chart from a DataFrame."""
        import plotly.express as px

        required_columns = [x, y]
        if color:
            required_columns.append(color)
        self._require_columns(dataframe, required_columns)
        chart_title = title or f"{y} par {x}"
        figure = px.bar(dataframe, x=x, y=y, color=color, title=chart_title)
        figure.update_layout(width=self.default_size[0], height=self.default_size[1])
        output_path = self._save_html(figure, path)
        return VisualizationResult(
            figure=figure,
            chart_type="bar",
            title=chart_title,
            interpretation=self._basic_interpretation(dataframe, x=x, y=y),
            output_path=output_path,
        )

    def line(
        self,
        dataframe: pd.DataFrame,
        x: str,
        y: str,
        color: str | None = None,
        title: str | None = None,
        path: str | Path | None = None,
    ) -> VisualizationResult:
        """Create a Plotly Express line chart for temporal or ordered data."""
        import plotly.express as px

        required_columns = [x, y]
        if color:
            required_columns.append(color)
        self._require_columns(dataframe, required_columns)
        chart_title = title or f"Evolution de {y}"
        figure = px.line(dataframe, x=x, y=y, color=color, markers=True, title=chart_title)
        figure.update_layout(width=self.default_size[0], height=self.default_size[1])
        output_path = self._save_html(figure, path)
        return VisualizationResult(
            figure=figure,
            chart_type="line",
            title=chart_title,
            interpretation=f"Le graphique montre l'evolution de `{y}` selon `{x}`.",
            output_path=output_path,
        )

    def auto_plot(
        self,
        dataframe: pd.DataFrame,
        question: str,
        path: str | Path | None = None,
    ) -> VisualizationResult:
        """Choose a reasonable Plotly chart from the user's question and DataFrame columns."""
        if dataframe.empty:
            raise ValueError("Cannot visualize an empty DataFrame.")

        lowered = question.lower()
        numeric_columns = list(dataframe.select_dtypes(include="number").columns)
        non_numeric_columns = [col for col in dataframe.columns if col not in numeric_columns]

        if any(word in lowered for word in ("evolution", "tendance", "temps", "date")):
            x = self._first_matching(dataframe.columns, ("date", "week", "month", "jour")) or dataframe.columns[0]
            y = numeric_columns[0] if numeric_columns else dataframe.columns[-1]
            return self.line(dataframe, x=x, y=y, title=self._title_from_question(question), path=path)

        x = non_numeric_columns[0] if non_numeric_columns else dataframe.columns[0]
        y = numeric_columns[0] if numeric_columns else dataframe.columns[-1]
        color = non_numeric_columns[1] if len(non_numeric_columns) > 1 else None
        return self.bar(
            dataframe,
            x=x,
            y=y,
            color=color,
            title=self._title_from_question(question),
            path=path,
        )

    @staticmethod
    def _require_columns(dataframe: pd.DataFrame, columns: list[str | None]) -> None:
        missing = [column for column in columns if column and column not in dataframe.columns]
        if missing:
            raise ValueError(f"Missing columns for visualization: {', '.join(missing)}")

    @staticmethod
    def _first_matching(columns: pd.Index, patterns: tuple[str, ...]) -> str | None:
        for column in columns:
            if any(pattern in str(column).lower() for pattern in patterns):
                return str(column)
        return None

    @staticmethod
    def _title_from_question(question: str) -> str:
        cleaned = question.strip().rstrip("?")
        return cleaned[:1].upper() + cleaned[1:] if cleaned else "Visualisation RetainFlow"

    @staticmethod
    def _basic_interpretation(dataframe: pd.DataFrame, x: str, y: str) -> str:
        if dataframe.empty:
            return "Aucune donnee disponible pour ce graphique."
        top_row = dataframe.sort_values(y, ascending=False).iloc[0]
        return f"La valeur la plus elevee de `{y}` concerne `{top_row[x]}`."

    @staticmethod
    def _save_html(figure: Any, path: str | Path | None) -> Path | None:
        if path is None:
            return None
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        figure.write_html(output_path)
        return output_path
