"""Data leakage checks for churn modeling datasets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from retainflow.features.preprocessing import FEATURE_COLUMNS, TARGET_COLUMN
from retainflow.features.selection import ALWAYS_EXCLUDED_FEATURES

FORBIDDEN_FEATURES = {
    "churn_date",
    "customer_lifecycle_status",
    "days_to_churn_after_observation",
    "synthetic_churn_probability",
    "churn_risk_band",
    "label_reason",
    *ALWAYS_EXCLUDED_FEATURES,
}


@dataclass(frozen=True)
class LeakageFinding:
    check_name: str
    status: str
    severity: str
    details: dict[str, Any]


class DataLeakageAuditor:
    """Audit common leakage risks before model training."""

    def __init__(
        self,
        target_column: str = TARGET_COLUMN,
        forbidden_features: set[str] | None = None,
    ) -> None:
        self.target_column = target_column
        self.forbidden_features = forbidden_features or FORBIDDEN_FEATURES

    def audit(
        self,
        dataset: pd.DataFrame,
        feature_columns: list[str] | None = None,
    ) -> pd.DataFrame:
        features = feature_columns or FEATURE_COLUMNS
        findings = [
            self._forbidden_feature_check(features),
            self._target_in_features_check(features),
            self._churn_date_consistency_check(dataset),
            self._same_customer_across_splits_check(dataset),
            self._constant_or_perfect_feature_check(dataset, features),
        ]
        return pd.DataFrame([finding.__dict__ for finding in findings])

    def assert_no_critical_leakage(
        self,
        dataset: pd.DataFrame,
        feature_columns: list[str] | None = None,
    ) -> pd.DataFrame:
        report = self.audit(dataset, feature_columns)
        critical = report[(report["status"] == "failed") & (report["severity"] == "critical")]
        if not critical.empty:
            raise ValueError(f"Critical data leakage detected: {critical.to_dict(orient='records')}")
        return report

    def _forbidden_feature_check(self, features: list[str]) -> LeakageFinding:
        leaked = sorted(set(features).intersection(self.forbidden_features))
        return LeakageFinding(
            check_name="forbidden_features_not_in_model_contract",
            status="failed" if leaked else "passed",
            severity="critical" if leaked else "info",
            details={"forbidden_features_found": leaked},
        )

    def _target_in_features_check(self, features: list[str]) -> LeakageFinding:
        leaked = self.target_column in features
        return LeakageFinding(
            check_name="target_not_in_features",
            status="failed" if leaked else "passed",
            severity="critical" if leaked else "info",
            details={"target_column": self.target_column, "target_in_features": leaked},
        )

    def _churn_date_consistency_check(self, dataset: pd.DataFrame) -> LeakageFinding:
        required = {"observation_date", "churn_date", self.target_column}
        if not required <= set(dataset.columns):
            return LeakageFinding(
                check_name="churn_date_after_observation",
                status="skipped",
                severity="info",
                details={"missing_columns": sorted(required - set(dataset.columns))},
            )

        frame = dataset.copy()
        frame["observation_date"] = pd.to_datetime(frame["observation_date"], errors="coerce")
        frame["churn_date"] = pd.to_datetime(frame["churn_date"], errors="coerce")
        positives = frame[pd.to_numeric(frame[self.target_column], errors="coerce") == 1]
        invalid = positives[
            positives["churn_date"].notna()
            & (positives["churn_date"] < positives["observation_date"])
        ]
        return LeakageFinding(
            check_name="churn_date_after_observation",
            status="failed" if not invalid.empty else "passed",
            severity="critical" if not invalid.empty else "info",
            details={"invalid_positive_rows": int(len(invalid))},
        )

    def _same_customer_across_splits_check(self, dataset: pd.DataFrame) -> LeakageFinding:
        required = {"customer_id", "split_name"}
        if not required <= set(dataset.columns):
            return LeakageFinding(
                check_name="same_customer_across_temporal_splits",
                status="skipped",
                severity="info",
                details={"missing_columns": sorted(required - set(dataset.columns))},
            )

        split_counts = dataset.groupby("customer_id")["split_name"].nunique()
        repeated = int((split_counts > 1).sum())
        return LeakageFinding(
            check_name="same_customer_across_temporal_splits",
            status="warning" if repeated else "passed",
            severity="medium" if repeated else "info",
            details={
                "customers_seen_in_multiple_splits": repeated,
                "interpretation": "acceptable for temporal panel data, but not acceptable for random splitting",
            },
        )

    def _constant_or_perfect_feature_check(
        self,
        dataset: pd.DataFrame,
        features: list[str],
    ) -> LeakageFinding:
        available_features = [feature for feature in features if feature in dataset.columns]
        suspicious = []
        target = pd.to_numeric(dataset[self.target_column], errors="coerce")
        for feature in available_features:
            values = dataset[feature]
            if values.nunique(dropna=False) <= 1:
                continue
            if values.nunique(dropna=False) <= 20:
                encoded = values.astype(str)
                grouped = target.groupby(encoded).mean()
                if grouped.isin([0.0, 1.0]).all() and len(grouped) > 1:
                    suspicious.append(feature)
        return LeakageFinding(
            check_name="low_cardinality_features_not_perfect_target_proxy",
            status="failed" if suspicious else "passed",
            severity="high" if suspicious else "info",
            details={"suspicious_features": sorted(suspicious)},
        )
