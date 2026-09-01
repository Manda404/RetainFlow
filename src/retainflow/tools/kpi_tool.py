"""KPI tool for churn, priority queue, and retention monitoring."""

from __future__ import annotations

from retainflow.config import ChurnModelConfig
from retainflow.tools.sql_tool import SQLQueryResult, SQLTool


class KPITool:
    """Expose curated business KPIs as reusable SQL-backed methods."""

    def __init__(self, config: ChurnModelConfig, sql_tool: SQLTool | None = None) -> None:
        self.config = config
        self.sql_tool = sql_tool or SQLTool(config)

    def churn_rate_by_split(self) -> SQLQueryResult:
        """Return observed churn rate by temporal split."""
        return self.sql_tool.query(
            f"""
            SELECT
              split_name,
              count(*) AS rows,
              sum(churn_label) AS churn_rows,
              round(avg(churn_label)::numeric, 4) AS churn_rate
            FROM {self.config.label_fqn}
            GROUP BY split_name
            ORDER BY
              CASE split_name
                WHEN 'train' THEN 1
                WHEN 'validation' THEN 2
                WHEN 'backtest' THEN 3
                WHEN 'test' THEN 4
                ELSE 5
              END
            """
        )

    def priority_clients_by_region(self, limit: int = 20) -> SQLQueryResult:
        """Return high-priority retention candidates by French region."""
        return self.sql_tool.query(
            f"""
            SELECT
              region,
              priority_tier,
              count(*) AS clients,
              round(avg(churn_probability)::numeric, 4) AS avg_churn_probability,
              round(sum(expected_saved_value)::numeric, 2) AS expected_saved_value
            FROM {self.config.retention_queue_fqn}
            GROUP BY region, priority_tier
            ORDER BY expected_saved_value DESC, clients DESC
            """,
            limit=limit,
        )

    def priority_clients_by_agency(self, limit: int = 20) -> SQLQueryResult:
        """Return agencies with the largest urgent retention workload."""
        return self.sql_tool.query(
            f"""
            SELECT
              agency_name,
              region,
              priority_tier,
              count(*) AS clients,
              round(avg(churn_probability)::numeric, 4) AS avg_churn_probability,
              round(sum(expected_saved_value)::numeric, 2) AS expected_saved_value
            FROM {self.config.retention_queue_fqn}
            GROUP BY agency_name, region, priority_tier
            ORDER BY expected_saved_value DESC, clients DESC
            """,
            limit=limit,
        )

    def recommended_actions_distribution(self, limit: int = 20) -> SQLQueryResult:
        """Return the distribution of generated retention recommendations."""
        return self.sql_tool.query(
            f"""
            SELECT
              recommended_action_type,
              recommended_channel,
              count(*) AS recommendations,
              round(avg(priority_score)::numeric, 2) AS avg_priority_score,
              round(avg(churn_probability)::numeric, 4) AS avg_churn_probability
            FROM {self.config.retention_recommendation_fqn}
            GROUP BY recommended_action_type, recommended_channel
            ORDER BY recommendations DESC, avg_priority_score DESC
            """,
            limit=limit,
        )

    def weekly_contact_rate_by_agency(self, limit: int = 20) -> SQLQueryResult:
        """Return a weekly agency view for operational contact follow-up."""
        return self.sql_tool.query(
            f"""
            SELECT
              q.agency_name,
              q.region,
              count(*) AS clients_a_contacter,
              round(avg(q.churn_probability)::numeric, 4) AS avg_churn_probability,
              round(avg(CASE WHEN r.human_review_status = 'APPROVED' THEN 1 ELSE 0 END)::numeric, 4)
                AS taux_actions_validees
            FROM {self.config.retention_queue_fqn} q
            LEFT JOIN {self.config.retention_recommendation_fqn} r
              ON r.customer_id = q.customer_id
             AND r.observation_date = q.observation_date
             AND r.mlflow_run_id = q.mlflow_run_id
            WHERE q.scored_at >= date_trunc('week', current_date)
            GROUP BY q.agency_name, q.region
            ORDER BY clients_a_contacter DESC, avg_churn_probability DESC
            """,
            limit=limit,
        )
