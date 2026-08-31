"""SHAP explainability utilities for churn models."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from catboost import CatBoostClassifier, Pool

from retainflow.features.preprocessing import CATEGORICAL_FEATURES, FEATURE_COLUMNS, TARGET_COLUMN


class ShapExplainer:
    def __init__(
        self,
        model: CatBoostClassifier,
        feature_names: list[str] | None = None,
        target_name: str = TARGET_COLUMN,
    ) -> None:
        self.model = model
        self.feature_names = feature_names or FEATURE_COLUMNS
        self.target_name = target_name

    def shap_values(self, pool: Pool, sample_size: int = 1000) -> pd.DataFrame:
        sample_pool = pool.slice(list(range(min(sample_size, pool.num_row()))))
        shap_values = self.model.get_feature_importance(sample_pool, type="ShapValues")
        return pd.DataFrame(shap_values[:, :-1], columns=self.feature_names)

    def summary_frame(self, pool: Pool, sample_size: int = 1000) -> pd.DataFrame:
        values = self.shap_values(pool, sample_size=sample_size)
        summary = pd.DataFrame(
            {
                "feature": self.feature_names,
                "feature_type": [
                    "categorical" if feature in CATEGORICAL_FEATURES else "numeric"
                    for feature in self.feature_names
                ],
                "mean_abs_shap": values.abs().mean().values,
                "mean_shap": values.mean().values,
                "positive_impact_share": (values > 0).mean().values,
            }
        )
        total_importance = float(summary["mean_abs_shap"].sum())
        if total_importance > 0:
            summary["normalized_importance_pct"] = (
                summary["mean_abs_shap"] / total_importance * 100
            )
        else:
            summary["normalized_importance_pct"] = 0.0
        summary["impact_direction"] = summary["mean_shap"].map(self._impact_direction)
        summary = summary.sort_values("mean_abs_shap", ascending=False).reset_index(drop=True)
        summary.insert(0, "rank", range(1, len(summary) + 1))
        return summary

    def build_agent_report(
        self,
        summary: pd.DataFrame,
        metrics_by_split: dict[str, dict[str, float]] | None = None,
        model_name: str = "retainflow_churn_catboost",
        run_id: str | None = None,
        sample_size: int = 1000,
        top_n: int = 20,
    ) -> dict[str, Any]:
        top_features = summary.head(top_n).to_dict(orient="records")
        return {
            "schema_version": "1.0",
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "model_name": model_name,
            "mlflow_run_id": run_id,
            "target": self.target_name,
            "explainability_method": "CatBoost SHAP values",
            "sample_size": sample_size,
            "interpretation_contract": {
                "mean_abs_shap": "Global feature importance. Higher means the feature contributes more to model output.",
                "mean_shap": "Average signed contribution. Positive values push churn risk up, negative values push it down.",
                "positive_impact_share": "Share of sampled rows where the feature increased predicted churn risk.",
                "normalized_importance_pct": "Relative global importance across all model features.",
            },
            "metrics_by_split": metrics_by_split or {},
            "top_features": top_features,
        }

    def save_summary_csv(self, summary: pd.DataFrame, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        summary.to_csv(path, index=False)
        return path

    def save_agent_report(self, report: dict[str, Any], path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, default=self._json_default), encoding="utf-8")
        return path

    def plot_feature_importance(self, summary: pd.DataFrame, path: Path, top_n: int = 20) -> Path:
        import matplotlib.pyplot as plt

        path.parent.mkdir(parents=True, exist_ok=True)
        plot_data = summary.head(top_n).sort_values("mean_abs_shap", ascending=True)
        ax = plot_data.plot.barh(
            x="feature",
            y="mean_abs_shap",
            figsize=(10, 7),
            legend=False,
            color="#2f6f8f",
        )
        ax.set_title("SHAP feature importance - churn model")
        ax.set_xlabel("mean absolute SHAP value")
        ax.set_ylabel("")
        plt.tight_layout()
        plt.savefig(path, dpi=160, bbox_inches="tight")
        plt.close()
        return path

    @staticmethod
    def _impact_direction(mean_shap: float) -> str:
        if mean_shap > 0:
            return "increases_churn_risk"
        if mean_shap < 0:
            return "decreases_churn_risk"
        return "mixed_or_neutral"

    @staticmethod
    def _json_default(value: Any) -> Any:
        if hasattr(value, "item"):
            return value.item()
        if isinstance(value, Path):
            return str(value)
        raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")
