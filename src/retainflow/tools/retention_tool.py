"""Tools for reading retention priority and recommendation outputs."""

from __future__ import annotations

from retainflow.config import ChurnModelConfig
from retainflow.tools.sql_tool import SQLQueryResult, SQLTool


class RetentionTool:
    """Read priority customers and recommendations prepared by RetainFlow."""

    def __init__(self, config: ChurnModelConfig, sql_tool: SQLTool | None = None) -> None:
        self.config = config
        self.sql_tool = sql_tool or SQLTool(config)

    def top_priority_clients(self, limit: int = 5) -> SQLQueryResult:
        """Return the most urgent clients to contact, ordered by priority score."""
        return self.sql_tool.query(
            f"""
            SELECT
              customer_id,
              first_name,
              last_name,
              split_name,
              region,
              agency_name,
              main_product_family,
              priority_tier,
              priority_score,
              churn_probability,
              expected_saved_value,
              recommended_action_type,
              recommended_channel,
              action_reason,
              business_context,
              mlflow_run_id
            FROM {self.config.retention_queue_fqn}
            ORDER BY priority_score DESC, expected_saved_value DESC, churn_probability DESC
            """,
            limit=limit,
        )

    def top_recommendations(self, limit: int = 5) -> SQLQueryResult:
        """Return human-reviewable recommendations for the top priority clients."""
        return self.sql_tool.query(
            f"""
            SELECT
              recommendation_id,
              customer_id,
              first_name,
              last_name,
              priority_tier,
              priority_score,
              churn_probability,
              expected_saved_value,
              recommended_action_type,
              recommended_channel,
              recommended_offer,
              estimated_offer_value,
              advisor_message,
              decision_rationale,
              next_best_step,
              human_review_status,
              mlflow_run_id
            FROM {self.config.retention_recommendation_fqn}
            ORDER BY priority_score DESC, expected_saved_value DESC, churn_probability DESC
            """,
            limit=limit,
        )
