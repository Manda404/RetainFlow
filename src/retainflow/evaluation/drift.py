"""Dataset drift analysis and HTML dashboard generation."""

from __future__ import annotations

import html
import json
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.spatial.distance import jensenshannon
from scipy.stats import ks_2samp

from retainflow.features.preprocessing import (
    CATEGORICAL_FEATURES,
    FEATURE_COLUMNS,
    NUMERIC_FEATURES,
    TARGET_COLUMN,
)


@dataclass(frozen=True)
class DriftThresholds:
    moderate_psi: float = 0.10
    high_psi: float = 0.25
    moderate_ks: float = 0.10
    high_ks: float = 0.20
    moderate_missing_delta: float = 0.05
    high_missing_delta: float = 0.15


class DriftAnalyzer:
    """Compare train, validation, test and backtest feature distributions."""

    def __init__(
        self,
        feature_columns: list[str] | None = None,
        numeric_features: list[str] | None = None,
        categorical_features: list[str] | None = None,
        split_column: str = "split_name",
        target_column: str = TARGET_COLUMN,
        reference_split: str = "train",
        split_order: tuple[str, ...] = ("train", "validation", "backtest", "test"),
        thresholds: DriftThresholds | None = None,
    ) -> None:
        self.feature_columns = feature_columns or FEATURE_COLUMNS
        self.numeric_features = numeric_features or NUMERIC_FEATURES
        self.categorical_features = categorical_features or CATEGORICAL_FEATURES
        self.split_column = split_column
        self.target_column = target_column
        self.reference_split = reference_split
        self.split_order = split_order
        self.thresholds = thresholds or DriftThresholds()

    def analyze(self, dataset: pd.DataFrame) -> pd.DataFrame:
        rows = []
        for reference_split, comparison_split in self._comparison_pairs(dataset):
            reference = dataset[dataset[self.split_column] == reference_split]
            comparison = dataset[dataset[self.split_column] == comparison_split]
            if reference.empty or comparison.empty:
                continue

            for feature in self.feature_columns:
                if feature not in dataset.columns:
                    continue
                if feature in self.numeric_features:
                    rows.append(
                        self._numeric_drift_row(
                            reference_split,
                            comparison_split,
                            feature,
                            reference[feature],
                            comparison[feature],
                        )
                    )
                elif feature in self.categorical_features:
                    rows.append(
                        self._categorical_drift_row(
                            reference_split,
                            comparison_split,
                            feature,
                            reference[feature],
                            comparison[feature],
                        )
                    )

            if self.target_column in dataset.columns:
                rows.append(
                    self._target_drift_row(
                        reference_split,
                        comparison_split,
                        reference[self.target_column],
                        comparison[self.target_column],
                    )
                )

        return pd.DataFrame(rows).sort_values(
            ["is_reference_comparison", "severity_rank", "psi", "feature"],
            ascending=[False, False, False, True],
            ignore_index=True,
        )

    def summary(self, drift_report: pd.DataFrame) -> dict[str, Any]:
        if drift_report.empty:
            return {
                "total_comparisons": 0,
                "total_features": 0,
                "high_drift_features": 0,
                "moderate_drift_features": 0,
                "stable_features": 0,
                "top_drift_features": [],
            }

        reference_report = drift_report[drift_report["is_reference_comparison"]]
        if reference_report.empty:
            reference_report = drift_report

        feature_severity = (
            reference_report.sort_values(["feature", "severity_rank"])
            .groupby("feature", as_index=False)
            .tail(1)
        )
        severity_counts = feature_severity["severity"].value_counts().to_dict()
        top_features = (
            reference_report.sort_values(["severity_rank", "psi"], ascending=[False, False])
            .head(15)[
                [
                    "reference_split",
                    "comparison_split",
                    "feature",
                    "feature_type",
                    "psi",
                    "secondary_metric",
                    "missing_rate_delta",
                    "severity",
                ]
            ]
            .to_dict(orient="records")
        )
        return {
            "total_comparisons": int(drift_report[["reference_split", "comparison_split"]].drop_duplicates().shape[0]),
            "total_features": int(reference_report["feature"].nunique()),
            "high_drift_features": int(severity_counts.get("high", 0)),
            "moderate_drift_features": int(severity_counts.get("moderate", 0)),
            "stable_features": int(severity_counts.get("stable", 0)),
            "top_drift_features": top_features,
        }

    def _comparison_pairs(self, dataset: pd.DataFrame) -> list[tuple[str, str]]:
        available = [
            split_name
            for split_name in self.split_order
            if split_name in set(dataset[self.split_column].astype(str))
        ]
        reference_pairs = [
            (self.reference_split, split_name)
            for split_name in available
            if split_name != self.reference_split and self.reference_split in available
        ]
        all_pairs = [
            pair for pair in combinations(available, 2) if pair not in set(reference_pairs)
        ]
        return reference_pairs + all_pairs

    def _numeric_drift_row(
        self,
        reference_split: str,
        comparison_split: str,
        feature: str,
        reference: pd.Series,
        comparison: pd.Series,
    ) -> dict[str, Any]:
        reference_numeric = pd.to_numeric(reference, errors="coerce")
        comparison_numeric = pd.to_numeric(comparison, errors="coerce")
        psi = self._numeric_psi(reference_numeric, comparison_numeric)
        ks_statistic, ks_pvalue = self._ks(reference_numeric, comparison_numeric)
        missing_rate_delta = abs(reference_numeric.isna().mean() - comparison_numeric.isna().mean())
        severity, severity_rank = self._severity(psi, ks_statistic, missing_rate_delta)
        return {
            "reference_split": reference_split,
            "comparison_split": comparison_split,
            "feature": feature,
            "feature_type": "numeric",
            "psi": psi,
            "secondary_metric_name": "ks_statistic",
            "secondary_metric": ks_statistic,
            "secondary_pvalue": ks_pvalue,
            "reference_missing_rate": float(reference_numeric.isna().mean()),
            "comparison_missing_rate": float(comparison_numeric.isna().mean()),
            "missing_rate_delta": float(missing_rate_delta),
            "reference_mean": self._safe_mean(reference_numeric),
            "comparison_mean": self._safe_mean(comparison_numeric),
            "reference_top_value": "",
            "comparison_top_value": "",
            "severity": severity,
            "severity_rank": severity_rank,
            "is_reference_comparison": reference_split == self.reference_split,
        }

    def _categorical_drift_row(
        self,
        reference_split: str,
        comparison_split: str,
        feature: str,
        reference: pd.Series,
        comparison: pd.Series,
    ) -> dict[str, Any]:
        reference_values = reference.fillna("__MISSING__").astype(str)
        comparison_values = comparison.fillna("__MISSING__").astype(str)
        reference_distribution, comparison_distribution = self._aligned_distributions(
            reference_values,
            comparison_values,
        )
        psi = self._psi(reference_distribution, comparison_distribution)
        js_distance = float(jensenshannon(reference_distribution, comparison_distribution))
        missing_rate_delta = abs(reference.isna().mean() - comparison.isna().mean())
        severity, severity_rank = self._severity(psi, js_distance, missing_rate_delta)
        return {
            "reference_split": reference_split,
            "comparison_split": comparison_split,
            "feature": feature,
            "feature_type": "categorical",
            "psi": psi,
            "secondary_metric_name": "jensen_shannon_distance",
            "secondary_metric": js_distance,
            "secondary_pvalue": np.nan,
            "reference_missing_rate": float(reference.isna().mean()),
            "comparison_missing_rate": float(comparison.isna().mean()),
            "missing_rate_delta": float(missing_rate_delta),
            "reference_mean": np.nan,
            "comparison_mean": np.nan,
            "reference_top_value": self._top_value(reference_values),
            "comparison_top_value": self._top_value(comparison_values),
            "severity": severity,
            "severity_rank": severity_rank,
            "is_reference_comparison": reference_split == self.reference_split,
        }

    def _target_drift_row(
        self,
        reference_split: str,
        comparison_split: str,
        reference: pd.Series,
        comparison: pd.Series,
    ) -> dict[str, Any]:
        reference_numeric = pd.to_numeric(reference, errors="coerce")
        comparison_numeric = pd.to_numeric(comparison, errors="coerce")
        reference_rate = self._safe_mean(reference_numeric)
        comparison_rate = self._safe_mean(comparison_numeric)
        delta = abs(reference_rate - comparison_rate)
        psi = self._categorical_psi(reference_numeric, comparison_numeric)
        severity, severity_rank = self._severity(psi, delta, 0.0)
        return {
            "reference_split": reference_split,
            "comparison_split": comparison_split,
            "feature": self.target_column,
            "feature_type": "target",
            "psi": psi,
            "secondary_metric_name": "churn_rate_delta",
            "secondary_metric": float(delta),
            "secondary_pvalue": np.nan,
            "reference_missing_rate": float(reference_numeric.isna().mean()),
            "comparison_missing_rate": float(comparison_numeric.isna().mean()),
            "missing_rate_delta": 0.0,
            "reference_mean": float(reference_rate),
            "comparison_mean": float(comparison_rate),
            "reference_top_value": "",
            "comparison_top_value": "",
            "severity": severity,
            "severity_rank": severity_rank,
            "is_reference_comparison": reference_split == self.reference_split,
        }

    def _severity(
        self,
        psi: float,
        secondary_metric: float,
        missing_rate_delta: float,
    ) -> tuple[str, int]:
        if (
            psi >= self.thresholds.high_psi
            or secondary_metric >= self.thresholds.high_ks
            or missing_rate_delta >= self.thresholds.high_missing_delta
        ):
            return "high", 3
        if (
            psi >= self.thresholds.moderate_psi
            or secondary_metric >= self.thresholds.moderate_ks
            or missing_rate_delta >= self.thresholds.moderate_missing_delta
        ):
            return "moderate", 2
        return "stable", 1

    def _numeric_psi(self, reference: pd.Series, comparison: pd.Series) -> float:
        ref = reference.dropna()
        cmp = comparison.dropna()
        if ref.empty or cmp.empty:
            return 0.0

        quantiles = np.linspace(0, 1, 11)
        bins = np.unique(ref.quantile(quantiles).to_numpy(dtype=float))
        if len(bins) < 3:
            return self._categorical_psi(reference, comparison)

        bins[0] = -np.inf
        bins[-1] = np.inf
        ref_counts = pd.cut(ref, bins=bins, include_lowest=True).value_counts(sort=False)
        cmp_counts = pd.cut(cmp, bins=bins, include_lowest=True).value_counts(sort=False)
        return self._psi(
            ref_counts.to_numpy(dtype=float) / max(ref_counts.sum(), 1),
            cmp_counts.to_numpy(dtype=float) / max(cmp_counts.sum(), 1),
        )

    def _categorical_psi(self, reference: pd.Series, comparison: pd.Series) -> float:
        reference_values = reference.fillna("__MISSING__").astype(str)
        comparison_values = comparison.fillna("__MISSING__").astype(str)
        reference_distribution, comparison_distribution = self._aligned_distributions(
            reference_values,
            comparison_values,
        )
        return self._psi(reference_distribution, comparison_distribution)

    def _aligned_distributions(
        self,
        reference: pd.Series,
        comparison: pd.Series,
    ) -> tuple[np.ndarray, np.ndarray]:
        categories = sorted(set(reference.unique()).union(set(comparison.unique())))
        ref_counts = reference.value_counts(normalize=True).reindex(categories, fill_value=0.0)
        cmp_counts = comparison.value_counts(normalize=True).reindex(categories, fill_value=0.0)
        return ref_counts.to_numpy(dtype=float), cmp_counts.to_numpy(dtype=float)

    def _psi(self, reference_distribution: np.ndarray, comparison_distribution: np.ndarray) -> float:
        epsilon = 1e-6
        reference_distribution = np.clip(reference_distribution, epsilon, None)
        comparison_distribution = np.clip(comparison_distribution, epsilon, None)
        return float(
            np.sum(
                (comparison_distribution - reference_distribution)
                * np.log(comparison_distribution / reference_distribution)
            )
        )

    def _ks(self, reference: pd.Series, comparison: pd.Series) -> tuple[float, float]:
        ref = reference.dropna()
        cmp = comparison.dropna()
        if ref.empty or cmp.empty:
            return 0.0, 1.0
        result = ks_2samp(ref, cmp, method="asymp")
        return float(result.statistic), float(result.pvalue)

    def _safe_mean(self, series: pd.Series) -> float:
        mean = series.mean()
        return float(mean) if pd.notna(mean) else 0.0

    def _top_value(self, series: pd.Series) -> str:
        counts = series.value_counts()
        if counts.empty:
            return ""
        return str(counts.index[0])


class DriftDashboardBuilder:
    """Build a standalone HTML dashboard from a drift report."""

    def __init__(self, title: str = "RetainFlow - Dashboard de drift") -> None:
        self.title = title

    def save(
        self,
        drift_report: pd.DataFrame,
        summary: dict[str, Any],
        dashboard_path: str | Path,
        summary_path: str | Path | None = None,
    ) -> Path:
        output_path = Path(dashboard_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(self.to_html(drift_report, summary), encoding="utf-8")

        if summary_path is not None:
            summary_output_path = Path(summary_path)
            summary_output_path.parent.mkdir(parents=True, exist_ok=True)
            summary_output_path.write_text(
                json.dumps(summary, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        return output_path

    def to_html(self, drift_report: pd.DataFrame, summary: dict[str, Any]) -> str:
        reference_report = drift_report[drift_report["is_reference_comparison"]]
        if reference_report.empty:
            reference_report = drift_report
        high_report = reference_report[reference_report["severity"] == "high"].head(30)
        moderate_report = reference_report[reference_report["severity"] == "moderate"].head(30)

        return f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(self.title)}</title>
  <style>
    body {{ margin: 0; font-family: Arial, sans-serif; color: #111827; background: #F8FAFC; }}
    header {{ background: #0F172A; color: white; padding: 28px 36px; }}
    main {{ padding: 28px 36px 44px; }}
    h1 {{ margin: 0 0 8px; font-size: 28px; }}
    h2 {{ margin: 28px 0 12px; font-size: 20px; }}
    p {{ margin: 0; color: #CBD5E1; }}
    .grid {{ display: grid; grid-template-columns: repeat(5, minmax(140px, 1fr)); gap: 12px; }}
    .card {{ background: white; border: 1px solid #E5E7EB; border-radius: 8px; padding: 14px; }}
    .metric {{ color: #64748B; font-size: 12px; text-transform: uppercase; }}
    .value {{ font-size: 24px; font-weight: 700; margin-top: 8px; }}
    table {{ width: 100%; border-collapse: collapse; background: white; border: 1px solid #E5E7EB; }}
    th, td {{ padding: 9px 10px; border-bottom: 1px solid #E5E7EB; font-size: 13px; text-align: left; }}
    th {{ background: #F1F5F9; color: #334155; position: sticky; top: 0; }}
    .stable {{ color: #166534; font-weight: 700; }}
    .moderate {{ color: #A16207; font-weight: 700; }}
    .high {{ color: #B91C1C; font-weight: 700; }}
    .table-wrap {{ max-height: 560px; overflow: auto; border-radius: 8px; }}
    .note {{ color: #475569; margin: 8px 0 16px; }}
    @media (max-width: 900px) {{ .grid {{ grid-template-columns: repeat(2, 1fr); }} main, header {{ padding-left: 18px; padding-right: 18px; }} }}
  </style>
</head>
<body>
  <header>
    <h1>{html.escape(self.title)}</h1>
    <p>Comparaison des distributions entre train, validation, backtest et test.</p>
  </header>
  <main>
    <section class="grid">
      {self._metric_card("Comparaisons", summary["total_comparisons"])}
      {self._metric_card("Variables", summary["total_features"])}
      {self._metric_card("Drift fort", summary["high_drift_features"], "high")}
      {self._metric_card("Drift modere", summary["moderate_drift_features"], "moderate")}
      {self._metric_card("Stable", summary["stable_features"], "stable")}
    </section>

    <h2>Variables avec drift fort vs train</h2>
    <p class="note">PSI >= 0.25, KS/JS eleve ou changement important du taux de valeurs manquantes.</p>
    {self._table(high_report)}

    <h2>Variables avec drift modere vs train</h2>
    {self._table(moderate_report)}

    <h2>Top drift features pour l'agent</h2>
    {self._top_features_table(summary.get("top_drift_features", []))}

    <h2>Detail complet</h2>
    <p class="note">Les lignes incluent les comparaisons vs train et les comparaisons entre tous les sous-datasets.</p>
    {self._table(drift_report)}
  </main>
</body>
</html>
"""

    def _metric_card(self, label: str, value: Any, css_class: str = "") -> str:
        value_html = html.escape(str(value))
        label_html = html.escape(label)
        return f'<div class="card"><div class="metric">{label_html}</div><div class="value {css_class}">{value_html}</div></div>'

    def _top_features_table(self, rows: list[dict[str, Any]]) -> str:
        if not rows:
            return "<p class=\"note\">Aucune variable avec drift significatif.</p>"
        return self._table(pd.DataFrame(rows))

    def _table(self, frame: pd.DataFrame) -> str:
        if frame.empty:
            return "<p class=\"note\">Aucune ligne a afficher.</p>"
        display = frame.copy()
        numeric_columns = display.select_dtypes(include=["number"]).columns
        for column in numeric_columns:
            display[column] = display[column].map(lambda value: "" if pd.isna(value) else f"{value:.4f}")
        if "severity" in display.columns:
            display["severity"] = display["severity"].map(
                lambda value: f'<span class="{html.escape(str(value))}">{html.escape(str(value))}</span>'
            )
        return '<div class="table-wrap">' + display.to_html(
            index=False,
            escape=False,
            border=0,
        ) + "</div>"
