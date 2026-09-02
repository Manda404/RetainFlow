"""Tool for retrieving a complete customer profile for agent workflows."""

from __future__ import annotations

from retainflow.config import ChurnModelConfig
from retainflow.tools.sql_tool import SQLQueryResult, SQLTool


class CustomerProfileTool:
    """Load a customer profile with model, retention, and agency context.

    This tool is useful before explaining a prediction or drafting an action:
    the advisor needs the customer identity, portfolio context, latest churn
    prediction, and current retention recommendation in one table.
    """

    def __init__(self, config: ChurnModelConfig, sql_tool: SQLTool | None = None) -> None:
        self.config = config
        self.sql_tool = sql_tool or SQLTool(config)

    def by_customer_id(self, customer_id: str, limit: int = 1) -> SQLQueryResult:
        """Return profile rows for one customer ordered by latest observation date."""
        return self.sql_tool.query(
            f"""
            SELECT
              c.customer_id,
              c.first_name,
              c.last_name,
              c.customer_segment,
              c.estimated_income_band,
              c.digital_profile,
              c.price_sensitivity_score,
              c.service_sensitivity_score,
              c.loyalty_score,
              c.consent_email,
              c.consent_sms,
              c.consent_phone,
              a.agency_name,
              g.region,
              s.observation_date,
              s.tenure_months,
              s.active_policy_count,
              s.number_of_products,
              s.total_annual_premium,
              s.payment_incidents_6m,
              s.complaints_6m,
              s.days_since_last_contact,
              s.avg_satisfaction_score_12m,
              s.renewal_days_min,
              p.churn_probability,
              p.churn_risk_band,
              p.predicted_churn_label,
              p.mlflow_run_id,
              q.priority_tier,
              q.priority_score,
              q.recommended_action_type,
              q.recommended_channel,
              q.action_reason,
              r.recommended_offer,
              r.advisor_message,
              r.next_best_step
            FROM {self.config.schema_name}.dim_customer c
            JOIN {self.config.schema_name}.dim_agency a
              ON a.agency_id = c.home_agency_id
            JOIN {self.config.schema_name}.dim_geography g
              ON g.geography_id = c.geography_id
            LEFT JOIN {self.config.feature_fqn} s
              ON s.customer_id = c.customer_id
            LEFT JOIN {self.config.prediction_fqn} p
              ON p.customer_id = c.customer_id
             AND p.observation_date = s.observation_date
            LEFT JOIN {self.config.retention_queue_fqn} q
              ON q.customer_id = c.customer_id
             AND q.observation_date = s.observation_date
             AND q.mlflow_run_id = p.mlflow_run_id
            LEFT JOIN {self.config.retention_recommendation_fqn} r
              ON r.customer_id = c.customer_id
             AND r.observation_date = s.observation_date
             AND r.mlflow_run_id = p.mlflow_run_id
            WHERE c.customer_id = :customer_id
            ORDER BY s.observation_date DESC NULLS LAST
            """,
            params={"customer_id": customer_id},
            limit=limit,
        )
