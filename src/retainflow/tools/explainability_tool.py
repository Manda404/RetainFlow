"""Tools that expose model explainability artifacts to agents."""

from __future__ import annotations

import json
from typing import Any

import pandas as pd

from retainflow.config import ChurnModelConfig


class ExplainabilityTool:
    """Load SHAP reports generated during model training."""

    def __init__(self, config: ChurnModelConfig) -> None:
        self.config = config

    def global_shap_summary(self, top_n: int = 20) -> pd.DataFrame:
        """Return the top global SHAP features as a DataFrame."""
        if not self.config.shap_summary_path.exists():
            return pd.DataFrame()
        summary = pd.read_csv(self.config.shap_summary_path)
        return summary.head(top_n).copy()

    def agent_report(self) -> dict[str, Any]:
        """Return the JSON report prepared for agent explanations."""
        if not self.config.shap_agent_report_path.exists():
            return {}
        return json.loads(self.config.shap_agent_report_path.read_text(encoding="utf-8"))

    def top_business_drivers(self, top_n: int = 5) -> list[str]:
        """Convert global SHAP rows into short business-readable drivers."""
        summary = self.global_shap_summary(top_n=top_n)
        if summary.empty:
            return []
        return [
            f"{row.feature}: {row.impact_direction} ({row.normalized_importance_pct:.1f}%)"
            for row in summary.itertuples(index=False)
        ]
