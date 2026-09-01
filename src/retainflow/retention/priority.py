"""Retention priority queue construction."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

from retainflow.config import ChurnModelConfig
from retainflow.data.dataset import sqlalchemy_dsn
from retainflow.logging import get_logger

logger = get_logger(__name__)


class RetentionPriorityLoader:
    """Load the latest churn predictions with customer context."""

    def __init__(self, config: ChurnModelConfig) -> None:
        self.config = config

    def query(self, split_names: tuple[str, ...] = ("test", "backtest")) -> tuple[str, dict[str, str]]:
        split_filter = ", ".join(f":split_{index}" for index, _ in enumerate(split_names))
        split_params = {f"split_{index}": split for index, split in enumerate(split_names)}
        query = f"""
            WITH latest_run AS (
                SELECT mlflow_run_id
                FROM {self.config.prediction_fqn}
                ORDER BY scored_at DESC
                LIMIT 1
            )
            SELECT
                p.observation_date,
                p.customer_id,
                p.split_name,
                p.churn_probability,
                p.predicted_churn_label,
                p.churn_risk_band,
                p.model_name,
                p.model_version,
                p.mlflow_run_id,
                p.scored_at,
                c.first_name,
                c.last_name,
                c.customer_segment,
                c.estimated_income_band,
                c.digital_profile,
                c.price_sensitivity_score,
                c.service_sensitivity_score,
                c.digital_engagement_score,
                c.loyalty_score,
                c.claim_propensity_score,
                c.consent_email,
                c.consent_sms,
                c.consent_phone,
                preferred.channel_code AS preferred_channel_code,
                preferred.channel_name AS preferred_channel_name,
                a.agency_name,
                a.agency_type,
                g.region,
                g.urbanicity,
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
                s.highest_coverage_tier
            FROM {self.config.prediction_fqn} p
            JOIN latest_run lr
              ON lr.mlflow_run_id = p.mlflow_run_id
            JOIN {self.config.feature_fqn} s
              ON s.observation_date = p.observation_date
             AND s.customer_id = p.customer_id
            JOIN {self.config.schema_name}.dim_customer c
              ON c.customer_id = p.customer_id
            JOIN {self.config.schema_name}.dim_channel preferred
              ON preferred.channel_id = c.preferred_channel_id
            JOIN {self.config.schema_name}.dim_agency a
              ON a.agency_id = c.home_agency_id
            JOIN {self.config.schema_name}.dim_geography g
              ON g.geography_id = c.geography_id
            WHERE p.split_name IN ({split_filter})
            ORDER BY p.churn_probability DESC, s.customer_value_score DESC
        """
        return query, split_params

    def load(self, split_names: tuple[str, ...] = ("test", "backtest")) -> pd.DataFrame:
        logger.info("Loading retention candidates from latest churn prediction run")
        engine = create_engine(sqlalchemy_dsn(self.config.postgres_dsn))
        query, params = self.query(split_names=split_names)
        with engine.connect() as conn:
            candidates = pd.read_sql_query(text(query), conn, params=params)
        logger.info("Loaded retention candidates with shape=%s", candidates.shape)
        return candidates


class RetentionPriorityScorer:
    """Convert churn predictions into prioritized retention actions."""

    def __init__(
        self,
        top_n: int | None = None,
        score_scale: float = 100.0,
    ) -> None:
        self.top_n = top_n
        self.score_scale = score_scale

    def score(self, candidates: pd.DataFrame) -> pd.DataFrame:
        frame = candidates.copy()
        if frame.empty:
            return self._empty_queue()

        churn_probability = pd.to_numeric(frame["churn_probability"], errors="coerce").fillna(0.0)
        annual_value = pd.to_numeric(frame["total_annual_premium"], errors="coerce").fillna(0.0)
        customer_value = pd.to_numeric(frame["customer_value_score"], errors="coerce").fillna(0.0)
        active_policies = pd.to_numeric(frame["active_policy_count"], errors="coerce").fillna(0.0)
        value_score = annual_value.rank(pct=True).fillna(0.0)
        value_score = np.maximum(value_score, customer_value.clip(0, 1))

        retention_propensity = self._retention_propensity(frame)
        urgency_score = self._urgency_score(frame)
        business_priority_score = self._business_priority_score(frame)

        priority_score = self.score_scale * (
            0.42 * churn_probability
            + 0.24 * value_score
            + 0.16 * retention_propensity
            + 0.12 * urgency_score
            + 0.06 * business_priority_score
        )
        estimated_annual_value = annual_value * (1 + 0.04 * active_policies.clip(lower=0))
        expected_saved_value = estimated_annual_value * churn_probability * retention_propensity

        frame["estimated_annual_value"] = estimated_annual_value.round(2)
        frame["retention_propensity"] = retention_propensity.round(4)
        frame["priority_score"] = priority_score.round(2)
        frame["expected_saved_value"] = expected_saved_value.round(2)
        frame["priority_tier"] = frame["priority_score"].map(self._priority_tier)
        frame["recommended_action_type"] = frame.apply(self._recommended_action_type, axis=1)
        frame["recommended_channel"] = frame.apply(self._recommended_channel, axis=1)
        frame["estimated_offer_value"] = frame.apply(self._estimated_offer_value, axis=1).round(2)
        frame["action_reason"] = frame.apply(self._action_reason, axis=1)
        frame["business_context"] = frame.apply(self._business_context, axis=1)

        queue_columns = [
            "observation_date",
            "customer_id",
            "split_name",
            "first_name",
            "last_name",
            "customer_segment",
            "region",
            "agency_name",
            "main_product_family",
            "churn_probability",
            "churn_risk_band",
            "estimated_annual_value",
            "retention_propensity",
            "expected_saved_value",
            "priority_score",
            "priority_tier",
            "recommended_action_type",
            "recommended_channel",
            "estimated_offer_value",
            "action_reason",
            "business_context",
            "model_name",
            "model_version",
            "mlflow_run_id",
            "scored_at",
        ]
        queue = frame[queue_columns].sort_values(
            ["priority_score", "expected_saved_value", "churn_probability"],
            ascending=[False, False, False],
        )
        if self.top_n is not None:
            queue = queue.head(self.top_n)
        return queue.reset_index(drop=True)

    def _retention_propensity(self, frame: pd.DataFrame) -> pd.Series:
        loyalty = pd.to_numeric(frame["loyalty_score"], errors="coerce").fillna(0.4)
        acceptance = pd.to_numeric(
            frame["retention_acceptance_rate_12m"], errors="coerce"
        ).fillna(0.0)
        campaign = pd.to_numeric(frame["campaign_response_rate_6m"], errors="coerce").fillna(0.0)
        service_cases = pd.to_numeric(frame["service_case_count_12m"], errors="coerce").fillna(0.0)
        unresolved = pd.to_numeric(frame["unresolved_case_count_12m"], errors="coerce").fillna(0.0)
        price_sensitivity = pd.to_numeric(
            frame["price_sensitivity_score"], errors="coerce"
        ).fillna(0.5)
        propensity = (
            0.18
            + 0.28 * loyalty
            + 0.22 * acceptance
            + 0.16 * campaign
            - 0.06 * price_sensitivity
            - 0.025 * service_cases.clip(upper=6)
            - 0.04 * unresolved.clip(upper=4)
        )
        return propensity.clip(0.05, 0.9)

    def _urgency_score(self, frame: pd.DataFrame) -> pd.Series:
        renewal_days = pd.to_numeric(frame["renewal_days_min"], errors="coerce")
        urgency = pd.Series(0.2, index=frame.index)
        urgency = urgency.mask(renewal_days.le(15), 1.0)
        urgency = urgency.mask(renewal_days.gt(15) & renewal_days.le(45), 0.75)
        urgency = urgency.mask(renewal_days.gt(45) & renewal_days.le(90), 0.45)
        return urgency.fillna(0.2)

    def _business_priority_score(self, frame: pd.DataFrame) -> pd.Series:
        score = pd.Series(0.35, index=frame.index)
        segment = frame["customer_segment"].astype(str)
        coverage = frame["highest_coverage_tier"].astype(str)
        score = score.mask(segment.eq("HIGH_VALUE"), score + 0.35)
        score = score.mask(segment.eq("FAMILY_PROTECTOR"), score + 0.2)
        score = score.mask(coverage.eq("PREMIUM"), score + 0.15)
        return score.clip(0, 1)

    def _priority_tier(self, score: float) -> str:
        if score >= 65:
            return "CRITICAL"
        if score >= 50:
            return "HIGH"
        if score >= 35:
            return "MEDIUM"
        return "LOW"

    def _recommended_action_type(self, row: pd.Series) -> str:
        if row["premium_increase_pct_max_12m"] >= 0.1 or row["competitor_price_index_avg_6m"] < 0.95:
            return "LOYALTY_DISCOUNT_REVIEW"
        if row["complaints_6m"] >= 2 or row["unresolved_case_count_12m"] >= 1:
            return "SERVICE_RECOVERY_CALL"
        if pd.notna(row["renewal_days_min"]) and row["renewal_days_min"] <= 45:
            return "RENEWAL_SAVE_CALL"
        if row["payment_incidents_6m"] >= 1 or row["rejected_payment_count_12m"] >= 1:
            return "PAYMENT_PLAN_PROPOSAL"
        if row["digital_sessions_30d"] <= 1 and row["email_open_rate_6m"] >= 0.25:
            return "DIGITAL_REENGAGEMENT"
        return "PROACTIVE_RETENTION_CHECK"

    def _recommended_channel(self, row: pd.Series) -> str:
        preferred = str(row["preferred_channel_code"])
        if preferred in {"CH_PHONE", "CH_AGENCY", "CH_RETENTION_OUTBOUND"} and row["consent_phone"]:
            return "PHONE"
        if preferred in {"CH_EMAIL", "CH_WEB", "CH_MOBILE"} and row["consent_email"]:
            return "EMAIL"
        if preferred == "CH_SMS" and row["consent_sms"]:
            return "SMS"
        if row["consent_phone"]:
            return "PHONE"
        if row["consent_email"]:
            return "EMAIL"
        if row["consent_sms"]:
            return "SMS"
        return "AGENCY_TASK"

    def _estimated_offer_value(self, row: pd.Series) -> float:
        annual_value = float(row["estimated_annual_value"])
        if row["priority_tier"] == "CRITICAL":
            return min(annual_value * 0.12, 300.0)
        if row["priority_tier"] == "HIGH":
            return min(annual_value * 0.08, 180.0)
        if row["priority_tier"] == "MEDIUM":
            return min(annual_value * 0.05, 90.0)
        return min(annual_value * 0.03, 40.0)

    def _action_reason(self, row: pd.Series) -> str:
        reasons = []
        if row["premium_increase_pct_max_12m"] >= 0.1:
            reasons.append("hausse de prime recente")
        if row["competitor_price_index_avg_6m"] < 0.95:
            reasons.append("pression tarifaire concurrente")
        if row["complaints_6m"] >= 2:
            reasons.append("reclamations recentes")
        if row["unresolved_case_count_12m"] >= 1:
            reasons.append("dossier service non resolu")
        if pd.notna(row["renewal_days_min"]) and row["renewal_days_min"] <= 45:
            reasons.append("renouvellement proche")
        if row["payment_incidents_6m"] >= 1:
            reasons.append("incident de paiement")
        if row["digital_sessions_30d"] <= 1:
            reasons.append("faible engagement digital")
        return "; ".join(reasons[:4]) or "risque churn eleve et valeur client significative"

    def _business_context(self, row: pd.Series) -> str:
        return (
            f"{row['customer_segment']} | {row['main_product_family']} | "
            f"{row['region']} | valeur annuelle estimee {row['estimated_annual_value']:.2f} EUR"
        )

    def _empty_queue(self) -> pd.DataFrame:
        return pd.DataFrame(
            columns=[
                "observation_date",
                "customer_id",
                "split_name",
                "priority_score",
                "priority_tier",
                "recommended_action_type",
                "recommended_channel",
            ]
        )


class RetentionPriorityRepository:
    """Persist retention priority queues to CSV and PostgreSQL."""

    def __init__(self, config: ChurnModelConfig) -> None:
        self.config = config

    def save_csv(self, queue: pd.DataFrame, path: str | Path | None = None) -> Path:
        output_path = Path(path or self.config.retention_queue_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        queue.to_csv(output_path, index=False)
        return output_path

    def save_postgres(self, queue: pd.DataFrame) -> None:
        logger.info("Saving %s retention priorities to %s", len(queue), self.config.retention_queue_fqn)
        engine = create_engine(sqlalchemy_dsn(self.config.postgres_dsn))
        with engine.begin() as conn:
            conn.execute(text(self._create_table_sql()))
            conn.execute(text(f"TRUNCATE TABLE {self.config.retention_queue_fqn}"))
            queue.to_sql(
                self.config.retention_queue_table,
                conn,
                schema=self.config.schema_name,
                if_exists="append",
                index=False,
                method="multi",
                chunksize=1000,
            )

    def _create_table_sql(self) -> str:
        return f"""
            CREATE TABLE IF NOT EXISTS {self.config.retention_queue_fqn} (
              observation_date date NOT NULL,
              customer_id text NOT NULL,
              split_name text NOT NULL,
              first_name text NOT NULL,
              last_name text NOT NULL,
              customer_segment text NOT NULL,
              region text NOT NULL,
              agency_name text NOT NULL,
              main_product_family text NOT NULL,
              churn_probability numeric(8,6) NOT NULL,
              churn_risk_band text NOT NULL,
              estimated_annual_value numeric(12,2) NOT NULL,
              retention_propensity numeric(8,4) NOT NULL,
              expected_saved_value numeric(12,2) NOT NULL,
              priority_score numeric(8,2) NOT NULL,
              priority_tier text NOT NULL,
              recommended_action_type text NOT NULL,
              recommended_channel text NOT NULL,
              estimated_offer_value numeric(12,2) NOT NULL,
              action_reason text NOT NULL,
              business_context text NOT NULL,
              model_name text NOT NULL,
              model_version text,
              mlflow_run_id text NOT NULL,
              scored_at timestamptz NOT NULL,
              queued_at timestamptz NOT NULL DEFAULT now(),
              PRIMARY KEY (observation_date, customer_id, mlflow_run_id)
            )
        """
