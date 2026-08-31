"""Business feature engineering for churn modeling."""

from __future__ import annotations

import numpy as np
import pandas as pd

ENGINEERED_NUMERIC_FEATURES = [
    "customer_age_years",
    "customer_lifetime_days",
    "observation_year",
    "observation_month",
    "observation_quarter",
    "premium_per_policy",
    "claim_amount_per_claim_12m",
    "payment_incident_rate_per_policy",
    "complaint_rate_per_interaction",
    "digital_engagement_gap",
    "value_minus_price_sensitivity",
    "renewal_urgency_score",
]

ENGINEERED_CATEGORICAL_FEATURES = [
    "renewal_window",
]

LABEL_AUDIT_COLUMNS = [
    "churn_date",
    "customer_lifecycle_status",
    "days_to_churn_after_observation",
]


class ChurnFeatureEngineer:
    def transform(self, dataset: pd.DataFrame) -> pd.DataFrame:
        frame = dataset.copy()
        observation_date = pd.to_datetime(frame["observation_date"], errors="coerce")
        birth_date = pd.to_datetime(frame["birth_date"], errors="coerce")
        acquisition_date = pd.to_datetime(frame["acquisition_date"], errors="coerce")
        churn_date = pd.to_datetime(frame.get("churn_date"), errors="coerce")

        frame["customer_age_years"] = ((observation_date - birth_date).dt.days / 365.25).round(2)
        frame["customer_lifetime_days"] = (observation_date - acquisition_date).dt.days.clip(lower=0)
        frame["observation_year"] = observation_date.dt.year
        frame["observation_month"] = observation_date.dt.month
        frame["observation_quarter"] = observation_date.dt.quarter

        frame["premium_per_policy"] = self._safe_divide(
            frame["total_annual_premium"],
            frame["active_policy_count"],
        )
        frame["claim_amount_per_claim_12m"] = self._safe_divide(
            frame["total_claim_amount_12m"],
            frame["total_claims_12m"],
        )
        frame["payment_incident_rate_per_policy"] = self._safe_divide(
            frame["payment_incidents_6m"],
            frame["active_policy_count"],
        )
        frame["complaint_rate_per_interaction"] = self._safe_divide(
            frame["complaints_6m"],
            frame["interactions_3m"],
        )
        frame["digital_engagement_gap"] = (
            pd.to_numeric(frame["digital_engagement_score"], errors="coerce")
            - pd.to_numeric(frame["email_open_rate_6m"], errors="coerce")
        )
        frame["value_minus_price_sensitivity"] = (
            pd.to_numeric(frame["customer_value_score"], errors="coerce")
            - pd.to_numeric(frame["price_sensitivity_score"], errors="coerce")
        )
        renewal_days = pd.to_numeric(frame["renewal_days_min"], errors="coerce")
        frame["renewal_urgency_score"] = (1 - (renewal_days.clip(lower=0, upper=365) / 365)).fillna(0)
        frame["renewal_window"] = pd.cut(
            renewal_days,
            bins=[-1, 30, 90, 180, 365, float("inf")],
            labels=["0_30_DAYS", "31_90_DAYS", "91_180_DAYS", "181_365_DAYS", "NO_NEAR_RENEWAL"],
        ).astype("object")
        frame["renewal_window"] = frame["renewal_window"].fillna("NO_ACTIVE_POLICY")

        frame["days_to_churn_after_observation"] = (churn_date - observation_date).dt.days
        frame["customer_lifecycle_status"] = frame["customer_lifecycle_status"].fillna("ACTIVE_OBSERVED")
        return frame

    @staticmethod
    def _safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
        numerator_numeric = pd.to_numeric(numerator, errors="coerce")
        denominator_numeric = pd.to_numeric(denominator, errors="coerce").replace(0, np.nan)
        return (numerator_numeric / denominator_numeric).fillna(0.0).astype(float)
