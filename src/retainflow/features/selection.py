"""Feature selection driven by drift analysis."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from retainflow.features.engineering import (
    ENGINEERED_CATEGORICAL_FEATURES,
    ENGINEERED_NUMERIC_FEATURES,
)
from retainflow.features.preprocessing import (
    CATEGORICAL_FEATURES,
    FEATURE_COLUMNS,
    ID_COLUMNS,
    NUMERIC_FEATURES,
    SPLIT_COLUMN,
    TARGET_COLUMN,
)

PROTECTED_COLUMNS = {
    *ID_COLUMNS,
    SPLIT_COLUMN,
    TARGET_COLUMN,
    "birth_date",
    "acquisition_date",
    "churn_date",
    "customer_lifecycle_status",
    "days_to_churn_after_observation",
    "synthetic_churn_probability",
    "churn_risk_band",
    "label_reason",
}

ALWAYS_EXCLUDED_FEATURES = {
    "latent_churn_risk_band",
}

ENGINEERED_FEATURE_DEPENDENCIES = {
    "customer_age_years": {"birth_date"},
    "customer_lifetime_days": {"acquisition_date"},
    "premium_per_policy": {"total_annual_premium", "active_policy_count"},
    "claim_amount_per_claim_12m": {"total_claim_amount_12m", "total_claims_12m"},
    "payment_incident_rate_per_policy": {"payment_incidents_6m", "active_policy_count"},
    "complaint_rate_per_interaction": {"complaints_6m", "interactions_3m"},
    "digital_engagement_gap": {"digital_engagement_score", "email_open_rate_6m"},
    "value_minus_price_sensitivity": {"customer_value_score", "price_sensitivity_score"},
    "renewal_urgency_score": {"renewal_days_min"},
    "renewal_window": {"renewal_days_min"},
}


@dataclass(frozen=True)
class DriftFeatureSelection:
    features_to_remove: list[str]
    raw_columns_to_drop: list[str]
    selected_numeric_features: list[str]
    selected_categorical_features: list[str]
    selected_feature_columns: list[str]
    excluded_engineered_features: list[str]
    protected_columns: list[str]
    reasons: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "selection_policy": "remove_high_drift_features_vs_train",
            "always_excluded_features": sorted(ALWAYS_EXCLUDED_FEATURES),
            "features_to_remove": self.features_to_remove,
            "raw_columns_to_drop": self.raw_columns_to_drop,
            "selected_numeric_features": self.selected_numeric_features,
            "selected_categorical_features": self.selected_categorical_features,
            "selected_feature_columns": self.selected_feature_columns,
            "excluded_engineered_features": self.excluded_engineered_features,
            "protected_columns": self.protected_columns,
            "reasons": self.reasons,
        }


class DriftFeatureSelector:
    """Select stable model features from a drift report."""

    def __init__(
        self,
        drift_report: pd.DataFrame,
        severity_to_remove: str = "high",
        reference_split: str = "train",
        protected_columns: set[str] | None = None,
        numeric_features: list[str] | None = None,
        categorical_features: list[str] | None = None,
    ) -> None:
        self.drift_report = drift_report.copy()
        self.severity_to_remove = severity_to_remove
        self.reference_split = reference_split
        self.protected_columns = protected_columns or PROTECTED_COLUMNS
        self.numeric_features = numeric_features or NUMERIC_FEATURES
        self.categorical_features = categorical_features or CATEGORICAL_FEATURES

    @classmethod
    def from_csv(
        cls,
        drift_report_path: str | Path,
        severity_to_remove: str = "high",
        reference_split: str = "train",
    ) -> DriftFeatureSelector:
        return cls(
            drift_report=pd.read_csv(drift_report_path),
            severity_to_remove=severity_to_remove,
            reference_split=reference_split,
        )

    def build_selection(self, raw_dataset: pd.DataFrame | None = None) -> DriftFeatureSelection:
        to_remove = self._features_to_remove().union(ALWAYS_EXCLUDED_FEATURES)
        raw_columns = set(raw_dataset.columns) if raw_dataset is not None else set()
        raw_columns_to_drop = sorted(
            feature
            for feature in to_remove
            if feature in raw_columns and feature not in self.protected_columns
        )
        dependency_exclusions = self._dependency_exclusions(set(raw_columns_to_drop))
        all_features_to_remove = to_remove.union(dependency_exclusions)
        selected_numeric = [
            feature
            for feature in self.numeric_features
            if feature not in all_features_to_remove
            and (not raw_columns or feature not in raw_columns_to_drop)
        ]
        selected_categorical = [
            feature
            for feature in self.categorical_features
            if feature not in all_features_to_remove
            and (not raw_columns or feature not in raw_columns_to_drop)
        ]
        engineered_features = set(ENGINEERED_NUMERIC_FEATURES + ENGINEERED_CATEGORICAL_FEATURES)
        return DriftFeatureSelection(
            features_to_remove=sorted(all_features_to_remove),
            raw_columns_to_drop=raw_columns_to_drop,
            selected_numeric_features=selected_numeric,
            selected_categorical_features=selected_categorical,
            selected_feature_columns=selected_numeric + selected_categorical,
            excluded_engineered_features=sorted(all_features_to_remove.intersection(engineered_features)),
            protected_columns=sorted(self.protected_columns),
            reasons=self._reasons(to_remove),
        )

    def drop_raw_columns(
        self,
        raw_dataset: pd.DataFrame,
        selection: DriftFeatureSelection | None = None,
    ) -> pd.DataFrame:
        active_selection = selection or self.build_selection(raw_dataset)
        return raw_dataset.drop(columns=active_selection.raw_columns_to_drop, errors="ignore")

    def save_selection(
        self,
        selection: DriftFeatureSelection,
        path: str | Path,
    ) -> Path:
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(selection.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return output_path

    def _features_to_remove(self) -> set[str]:
        report = self.drift_report
        reference_report = report[
            (report["reference_split"].astype(str) == self.reference_split)
            & (report["severity"].astype(str) == self.severity_to_remove)
        ]
        if "is_reference_comparison" in report.columns:
            reference_report = reference_report[
                reference_report["is_reference_comparison"].astype(str).str.lower() == "true"
            ]
        return set(reference_report["feature"].dropna().astype(str)).intersection(FEATURE_COLUMNS)

    def _dependency_exclusions(self, raw_columns_to_drop: set[str]) -> set[str]:
        return {
            feature
            for feature, dependencies in ENGINEERED_FEATURE_DEPENDENCIES.items()
            if dependencies.intersection(raw_columns_to_drop)
        }

    def _reasons(self, features_to_remove: set[str]) -> list[dict[str, Any]]:
        report = self.drift_report[self.drift_report["feature"].isin(features_to_remove)].copy()
        if "is_reference_comparison" in report.columns:
            report = report[report["is_reference_comparison"].astype(str).str.lower() == "true"]
        report = report.sort_values(["feature", "severity_rank", "psi"], ascending=[True, False, False])
        keep_columns = [
            "feature",
            "feature_type",
            "reference_split",
            "comparison_split",
            "psi",
            "secondary_metric_name",
            "secondary_metric",
            "missing_rate_delta",
            "severity",
        ]
        return report[keep_columns].to_dict(orient="records")
