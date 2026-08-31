"""Load churn modeling data from PostgreSQL."""

from __future__ import annotations

import pandas as pd
from sqlalchemy import create_engine

from retainflow.config import ChurnModelConfig
from retainflow.logging import get_logger

logger = get_logger(__name__)


def sqlalchemy_dsn(dsn: str) -> str:
    if dsn.startswith("postgresql+psycopg://"):
        return dsn
    if dsn.startswith("postgresql://"):
        return dsn.replace("postgresql://", "postgresql+psycopg://", 1)
    return dsn


class ChurnDatasetLoader:
    def __init__(self, config: ChurnModelConfig) -> None:
        self.config = config

    def query(self) -> str:
        config = self.config
        return f"""
            SELECT
                s.observation_date,
                s.customer_id,
                s.split_name,
                s.tenure_months,
                s.active_policy_count,
                s.number_of_products,
                s.total_annual_premium,
                s.total_claims_12m,
                s.total_claim_amount_12m,
                s.payment_incidents_6m,
                s.complaints_6m,
                s.interactions_3m,
                s.days_since_last_contact,
                s.digital_sessions_30d,
                s.email_open_rate_6m,
                s.premium_increase_pct_max_12m,
                s.avg_satisfaction_score_12m,
                s.renewal_days_min,
                s.customer_value_score,
                s.customer_age_years AS snapshot_customer_age_years,
                s.active_auto_policy_count,
                s.active_home_policy_count,
                s.active_health_policy_count,
                s.active_life_policy_count,
                s.cancelled_policy_count_to_date,
                s.policy_age_avg_months,
                s.late_payment_count_12m,
                s.rejected_payment_count_12m,
                s.service_case_count_12m,
                s.unresolved_case_count_12m,
                s.retention_offer_count_12m,
                s.retention_acceptance_rate_12m,
                s.quote_count_6m,
                s.competitor_price_index_avg_6m,
                s.campaign_response_rate_6m,
                s.main_product_family,
                s.highest_coverage_tier,
                s.latent_churn_risk_band,
                c.birth_date,
                c.acquisition_date,
                c.customer_segment,
                c.estimated_income_band,
                c.digital_profile,
                c.price_sensitivity_score,
                c.service_sensitivity_score,
                c.digital_engagement_score,
                c.loyalty_score,
                c.claim_propensity_score,
                a.agency_type,
                g.region,
                g.urbanicity,
                l.churn_label,
                l.churn_date,
                l.customer_lifecycle_status,
                l.churn_probability AS synthetic_churn_probability,
                l.churn_risk_band,
                l.label_reason
            FROM {config.feature_fqn} s
            JOIN {config.label_fqn} l
              ON l.observation_date = s.observation_date
             AND l.customer_id = s.customer_id
            JOIN {config.schema_name}.dim_customer c
              ON c.customer_id = s.customer_id
            JOIN {config.schema_name}.dim_agency a
              ON a.agency_id = c.home_agency_id
            JOIN {config.schema_name}.dim_geography g
              ON g.geography_id = c.geography_id
            ORDER BY s.observation_date, s.customer_id
        """

    def load(self) -> pd.DataFrame:
        logger.info("Loading churn dataset from PostgreSQL: %s", self.config.postgres_dsn)
        engine = create_engine(sqlalchemy_dsn(self.config.postgres_dsn))
        with engine.connect() as conn:
            dataset = pd.read_sql_query(self.query(), conn)
        logger.info("Loaded churn dataset with shape=%s", dataset.shape)
        return dataset


def load_churn_dataset(config: ChurnModelConfig) -> pd.DataFrame:
    return ChurnDatasetLoader(config).load()
