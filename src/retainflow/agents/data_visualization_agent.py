"""Agent that turns SQL or model results into visual analytics."""

from __future__ import annotations

import pandas as pd

from retainflow.agents.base import AgentResponse
from retainflow.tools.visualization_tool import VisualizationResult, VisualizationTool


class DataVisualizationAgent:
    """Create charts from DataFrames, with Plotly Express as the default engine."""

    def __init__(self, visualization_tool: VisualizationTool | None = None) -> None:
        self.visualization_tool = visualization_tool or VisualizationTool()

    def answer(
        self,
        question: str,
        dataframe: pd.DataFrame,
        path: str | None = None,
    ) -> AgentResponse:
        """Generate a figure adapted to the question and available columns."""
        visual = self.visualization_tool.auto_plot(dataframe, question=question, path=path)
        return self._response(visual)

    def bar(
        self,
        dataframe: pd.DataFrame,
        x: str,
        y: str,
        color: str | None = None,
        title: str | None = None,
        path: str | None = None,
    ) -> AgentResponse:
        """Generate a bar chart with explicit column choices."""
        visual = self.visualization_tool.bar(
            dataframe=dataframe,
            x=x,
            y=y,
            color=color,
            title=title,
            path=path,
        )
        return self._response(visual)

    @staticmethod
    def _response(visual: VisualizationResult) -> AgentResponse:
        return AgentResponse(
            agent_name="DataVisualizationAgent",
            answer=visual.interpretation,
            data=visual.figure,
            metadata={
                "chart_type": visual.chart_type,
                "title": visual.title,
                "output_path": str(visual.output_path) if visual.output_path else None,
            },
        )
