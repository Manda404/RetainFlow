"""SQL agent that maps business questions to controlled SQL queries."""

from __future__ import annotations

from retainflow.agents.base import AgentResponse
from retainflow.config import ChurnModelConfig
from retainflow.tools.sql_tool import SQLQueryResult, SQLTool


class SQLAgent:
    """Build and execute governed SQL for common RetainFlow business questions.

    This first implementation is deterministic. Later, an LLM can propose SQL,
    but it should still pass through this agent and `SQLTool` validation before
    touching PostgreSQL.
    """

    def __init__(self, config: ChurnModelConfig, sql_tool: SQLTool | None = None) -> None:
        self.config = config
        self.sql_tool = sql_tool or SQLTool(config)

    def answer(self, question: str, limit: int = 20) -> AgentResponse:
        """Execute the best SQL template for a natural-language question."""
        sql = self.build_sql(question)
        result = self.sql_tool.query(sql, limit=limit)
        return AgentResponse(
            agent_name="SQLAgent",
            answer=f"Requete executee avec {result.row_count} lignes retournees.",
            data=result.dataframe,
            metadata={"sql": result.sql, "row_count": result.row_count, "truncated": result.truncated},
        )

    def execute_sql(self, sql: str, limit: int = 20) -> SQLQueryResult:
        """Execute an explicit SQL query after read-only validation."""
        return self.sql_tool.query(sql, limit=limit)

    def build_sql(self, question: str) -> str:
        """Select a curated SQL template from the question intent."""
        lowered = question.lower()
        if "agence" in lowered and any(word in lowered for word in ("contact", "semaine")):
            return self._weekly_contacts_by_agency_sql()
        if "region" in lowered or "région" in lowered:
            return self._priority_by_region_sql()
        if "action" in lowered or "recommand" in lowered:
            return self._recommended_actions_sql()
        return self._top_priority_clients_sql()

    def _top_priority_clients_sql(self) -> str:
        return f"""
            SELECT
              customer_id,
              first_name,
              last_name,
              region,
              agency_name,
              priority_tier,
              priority_score,
              churn_probability,
              expected_saved_value,
              recommended_action_type,
              recommended_channel,
              action_reason,
              mlflow_run_id
            FROM {self.config.retention_queue_fqn}
            ORDER BY priority_score DESC, expected_saved_value DESC, churn_probability DESC
        """

    def _priority_by_region_sql(self) -> str:
        return f"""
            SELECT
              region,
              priority_tier,
              count(*) AS clients,
              round(avg(churn_probability)::numeric, 4) AS avg_churn_probability,
              round(sum(expected_saved_value)::numeric, 2) AS expected_saved_value
            FROM {self.config.retention_queue_fqn}
            GROUP BY region, priority_tier
            ORDER BY expected_saved_value DESC, clients DESC
        """

    def _recommended_actions_sql(self) -> str:
        return f"""
            SELECT
              recommended_action_type,
              recommended_channel,
              count(*) AS recommendations,
              round(avg(priority_score)::numeric, 2) AS avg_priority_score,
              round(avg(churn_probability)::numeric, 4) AS avg_churn_probability
            FROM {self.config.retention_recommendation_fqn}
            GROUP BY recommended_action_type, recommended_channel
            ORDER BY recommendations DESC, avg_priority_score DESC
        """

    def _weekly_contacts_by_agency_sql(self) -> str:
        return f"""
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
        """
