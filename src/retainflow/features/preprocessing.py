"""Preprocessing and feature contracts for churn modeling."""

from __future__ import annotations

import pandas as pd

from retainflow.features.engineering import (
    ENGINEERED_CATEGORICAL_FEATURES,
    ENGINEERED_NUMERIC_FEATURES,
)

TARGET_COLUMN = "churn_label"
ID_COLUMNS = ["observation_date", "customer_id"]
SPLIT_COLUMN = "split_name"

CATEGORICAL_FEATURES = [
    "latent_churn_risk_band",
    "customer_segment",
    "estimated_income_band",
    "digital_profile",
    "agency_type",
    "region",
    "urbanicity",
    "main_product_family",
    "highest_coverage_tier",
]

NUMERIC_FEATURES = [
    "tenure_months",
    "active_policy_count",
    "number_of_products",
    "total_annual_premium",
    "total_claims_12m",
    "total_claim_amount_12m",
    "payment_incidents_6m",
    "complaints_6m",
    "interactions_3m",
    "days_since_last_contact",
    "digital_sessions_30d",
    "email_open_rate_6m",
    "premium_increase_pct_max_12m",
    "avg_satisfaction_score_12m",
    "renewal_days_min",
    "customer_value_score",
    "price_sensitivity_score",
    "service_sensitivity_score",
    "digital_engagement_score",
    "loyalty_score",
    "claim_propensity_score",
    "active_auto_policy_count",
    "active_home_policy_count",
    "active_health_policy_count",
    "active_life_policy_count",
    "cancelled_policy_count_to_date",
    "policy_age_avg_months",
    "late_payment_count_12m",
    "rejected_payment_count_12m",
    "service_case_count_12m",
    "unresolved_case_count_12m",
    "retention_offer_count_12m",
    "retention_acceptance_rate_12m",
    "quote_count_6m",
    "competitor_price_index_avg_6m",
    "campaign_response_rate_6m",
    *ENGINEERED_NUMERIC_FEATURES,
]

CATEGORICAL_FEATURES = CATEGORICAL_FEATURES + ENGINEERED_CATEGORICAL_FEATURES

FEATURE_COLUMNS = NUMERIC_FEATURES + CATEGORICAL_FEATURES


class ChurnPreprocessor:
    def __init__(
        self,
        numeric_features: list[str] | None = None,
        categorical_features: list[str] | None = None,
        target_column: str = TARGET_COLUMN,
    ) -> None:
        self.numeric_features = numeric_features or NUMERIC_FEATURES
        self.categorical_features = categorical_features or CATEGORICAL_FEATURES
        self.target_column = target_column
        self.numeric_fill_values: dict[str, float] = {}
        self.categorical_fill_values: dict[str, str] = {}
        self.is_fitted = False

    @property
    def feature_columns(self) -> list[str]:
        return self.numeric_features + self.categorical_features

    def fit(self, dataset: pd.DataFrame) -> ChurnPreprocessor:
        frame = dataset.copy()
        for column in self.numeric_features:
            values = pd.to_numeric(frame[column], errors="coerce")
            median = values.median()
            self.numeric_fill_values[column] = float(median) if pd.notna(median) else 0.0
        for column in self.categorical_features:
            values = frame[column].dropna().astype(str)
            self.categorical_fill_values[column] = values.mode().iloc[0] if not values.empty else "UNKNOWN"
        self.is_fitted = True
        return self

    def transform(self, dataset: pd.DataFrame) -> pd.DataFrame:
        if not self.is_fitted:
            raise RuntimeError("ChurnPreprocessor must be fitted on the train split before transform.")
        frame = dataset.copy()
        for column in self.numeric_features:
            frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(
                self.numeric_fill_values[column]
            )
        for column in self.categorical_features:
            frame[column] = frame[column].fillna(self.categorical_fill_values[column]).astype(str)
        frame[self.target_column] = frame[self.target_column].astype(int)
        return frame

    def fit_transform(self, dataset: pd.DataFrame) -> pd.DataFrame:
        return self.fit(dataset).transform(dataset)

    def catboost_feature_indices(self) -> list[int]:
        return [self.feature_columns.index(column) for column in self.categorical_features]


def prepare_model_frame(dataset: pd.DataFrame) -> pd.DataFrame:
    return ChurnPreprocessor().fit_transform(dataset)


def catboost_feature_indices() -> list[int]:
    return ChurnPreprocessor().catboost_feature_indices()
