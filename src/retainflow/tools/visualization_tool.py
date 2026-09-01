"""Visualization tool using Plotly Express first, with optional static fallbacks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

DISPLAY_LABELS = {
    "agency_name": "Branch",
    "avg_churn_probability": "Average churn probability",
    "clients": "Customers",
    "customers_to_contact": "Customers to contact",
    "expected_saved_value": "Expected saved value",
    "priority_tier": "Priority tier",
    "region": "Region",
}

PRIORITY_COLORS = {
    "CRITICAL": "#dc2626",
    "Critical": "#dc2626",
    "HIGH": "#f97316",
    "High": "#f97316",
    "MEDIUM": "#2563eb",
    "Medium": "#2563eb",
    "LOW": "#64748b",
    "Low": "#64748b",
}


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
        chart_title = title or f"{self._display_label(y)} by {self._display_label(x)}"
        horizontal = self._should_use_horizontal_bar(dataframe, x=x)
        plot_data = self._sorted_bar_data(dataframe, x=x, y=y)
        if color == "priority_tier":
            plot_data[color] = plot_data[color].map(lambda value: str(value).title())
        labels = self._labels_for(plot_data.columns)
        color_map = PRIORITY_COLORS if color == "priority_tier" else None

        if horizontal:
            figure = px.bar(
                plot_data,
                x=y,
                y=x,
                color=color,
                orientation="h",
                title=chart_title,
                labels=labels,
                color_discrete_map=color_map,
                text=y,
            )
        else:
            figure = px.bar(
                plot_data,
                x=x,
                y=y,
                color=color,
                title=chart_title,
                labels=labels,
                color_discrete_map=color_map,
                text=y,
            )

        figure.update_traces(
            hovertemplate="<b>%{y}</b><br>%{x}<extra></extra>" if horizontal else None,
            texttemplate="%{text:.0f}",
            textposition="outside" if not color else "auto",
        )
        figure.update_layout(
            width=self.default_size[0],
            height=max(self.default_size[1], 420),
            barmode="stack" if color else "relative",
            bargap=0.28,
            legend_title_text=self._display_label(color) if color else None,
            margin={"l": 145 if horizontal else 70, "r": 42, "t": 72, "b": 72},
            paper_bgcolor="white",
            plot_bgcolor="white",
            font={"family": "Inter, system-ui, sans-serif", "color": "#172033"},
            title={"font": {"size": 17}},
            xaxis={"showgrid": True, "gridcolor": "#e5edf4", "zeroline": False},
            yaxis={"showgrid": False, "categoryorder": "total ascending"},
        )
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
        chart_title = title or f"{y} trend"
        figure = px.line(dataframe, x=x, y=y, color=color, markers=True, title=chart_title)
        figure.update_layout(width=self.default_size[0], height=self.default_size[1])
        output_path = self._save_html(figure, path)
        return VisualizationResult(
            figure=figure,
            chart_type="line",
            title=chart_title,
            interpretation=f"The chart shows the evolution of `{y}` by `{x}`.",
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

        if any(word in lowered for word in ("evolution", "trend", "tendance", "time", "temps", "date")):
            x = self._first_matching(dataframe.columns, ("date", "week", "month", "jour")) or dataframe.columns[0]
            y = numeric_columns[0] if numeric_columns else dataframe.columns[-1]
            return self.line(dataframe, x=x, y=y, title=self._title_from_question(question), path=path)

        x = non_numeric_columns[0] if non_numeric_columns else dataframe.columns[0]
        y = self._preferred_numeric_column(numeric_columns, lowered) or (
            numeric_columns[0] if numeric_columns else dataframe.columns[-1]
        )
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
        lowered = cleaned.lower()
        if "priority" in lowered and "region" in lowered:
            return "Priority Customers by Region"
        if "priority" in lowered and ("agency" in lowered or "branch" in lowered):
            return "Priority Customers by Branch"
        return cleaned[:1].upper() + cleaned[1:] if cleaned else "RetainFlow visualization"

    @staticmethod
    def _basic_interpretation(dataframe: pd.DataFrame, x: str, y: str) -> str:
        if dataframe.empty:
            return "No data is available for this chart."
        top_row = dataframe.sort_values(y, ascending=False).iloc[0]
        metric = VisualizationTool._display_label(y).lower()
        if y in {"clients", "customers_to_contact"}:
            return f"The largest customer count is in {top_row[x]}."
        return f"The highest {metric} is for {top_row[x]}."

    @staticmethod
    def _display_label(column: str | None) -> str:
        if not column:
            return ""
        return DISPLAY_LABELS.get(column, str(column).replace("_", " ").title())

    @staticmethod
    def _labels_for(columns: pd.Index) -> dict[str, str]:
        return {str(column): VisualizationTool._display_label(str(column)) for column in columns}

    @staticmethod
    def _preferred_numeric_column(numeric_columns: list[str], lowered_question: str) -> str | None:
        if any(word in lowered_question for word in ("value", "revenue", "saved", "eur")):
            for column in ("expected_saved_value", "estimated_offer_value"):
                if column in numeric_columns:
                    return column
        if any(word in lowered_question for word in ("customer", "customers", "client", "clients")):
            for column in ("clients", "customers_to_contact"):
                if column in numeric_columns:
                    return column
        return None

    @staticmethod
    def _should_use_horizontal_bar(dataframe: pd.DataFrame, x: str) -> bool:
        if x in {"region", "agency_name"}:
            return True
        return dataframe[x].nunique(dropna=True) > 5

    @staticmethod
    def _sorted_bar_data(dataframe: pd.DataFrame, x: str, y: str) -> pd.DataFrame:
        totals = dataframe.groupby(x, dropna=False)[y].transform("sum")
        return dataframe.assign(_retainflow_sort_total=totals).sort_values(
            ["_retainflow_sort_total", x],
            ascending=[True, True],
        ).drop(columns="_retainflow_sort_total")

    @staticmethod
    def _save_html(figure: Any, path: str | Path | None) -> Path | None:
        if path is None:
            return None
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        figure.write_html(output_path)
        return output_path
