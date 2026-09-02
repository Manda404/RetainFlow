"""SQL agent that maps business questions to controlled SQL queries."""

from __future__ import annotations

import re

from retainflow.agents.activity import activity_item
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
        is_count = "total_customers" in result.dataframe.columns
        answer = f"Read-only query executed with {result.row_count} returned rows."
        business_type = "data_table"
        if is_count and not result.dataframe.empty:
            total = int(result.dataframe.iloc[0]["total_customers"])
            answer = f"La base contient {total:,} clients uniques.".replace(",", " ")
            business_type = "data_count"
        elif self._asks_for_customer_data(question.lower()):
            answer = f"{result.row_count} client(s) trouve(s) pour cette recherche."
            business_type = "data_query"
        return AgentResponse(
            agent_name="SQLAgent",
            answer=answer,
            data=result.dataframe,
            metadata={
                "sql": result.sql,
                "row_count": result.row_count,
                "truncated": result.truncated,
                "activity": [
                    activity_item(
                        id="step_1",
                        agent="SQLAgent",
                        tool="SQLTool",
                        business_label="Customer Data",
                        status="completed",
                        summary=f"Retrieved {result.row_count} rows from PostgreSQL.",
                        details={
                            "rows": result.row_count,
                            "truncated": result.truncated,
                            "sql": result.sql,
                        },
                    )
                ],
            },
            business_type=business_type,
        )

    def execute_sql(self, sql: str, limit: int = 20) -> SQLQueryResult:
        """Execute an explicit SQL query after read-only validation."""
        return self.sql_tool.query(sql, limit=limit)

    def build_sql(self, question: str) -> str:
        """Select a curated SQL template from the question intent."""
        lowered = question.lower()
        if self._asks_for_customer_count(lowered):
            return self._customer_count_sql()
        if self._asks_for_customer_data(lowered):
            return self._customer_lookup_sql(question)
        if any(word in lowered for word in ("agence", "agency")) and any(
            word in lowered for word in ("contact", "semaine", "week", "weekly")
        ):
            return self._weekly_contacts_by_agency_sql()
        if "region" in lowered or "région" in lowered:
            return self._priority_by_region_sql()
        if any(word in lowered for word in ("action", "recommend", "recommand")):
            return self._recommended_actions_sql()
        if self._asks_for_priority_customers(lowered):
            return self._top_priority_clients_sql()
        raise ValueError("SQLAgent cannot map this question to a safe curated SQL template.")

    @staticmethod
    def _asks_for_customer_count(lowered: str) -> bool:
        count_terms = ("combien", "nombre", "count", "volume", "total")
        customer_terms = ("client", "clients", "customer", "customers", "donnee client", "donnée client")
        database_terms = ("base", "database", "table", "donnee", "donnée")
        return (
            any(term in lowered for term in count_terms)
            and any(term in lowered for term in customer_terms)
            and any(term in lowered for term in database_terms)
        )

    @staticmethod
    def _asks_for_priority_customers(lowered: str) -> bool:
        priority_terms = (
            "priorite",
            "priorité",
            "prioritaires",
            "susceptibles",
            "risque",
            "risques",
            "churn",
            "attrition",
        )
        customer_terms = ("client", "clients", "customer", "customers")
        return any(term in lowered for term in priority_terms) and any(
            term in lowered for term in customer_terms
        )

    @staticmethod
    def _asks_for_customer_data(lowered: str) -> bool:
        customer_terms = ("client", "clients", "customer", "customers")
        data_terms = ("quel", "quels", "liste", "lister", "montre", "affiche", "trouve", "cherche", "ville", "region", "région", "agence")
        churn_terms = ("churn", "risque", "priorite", "priorité", "susceptible", "retention", "rétention")
        return (
            any(term in lowered for term in customer_terms)
            and any(term in lowered for term in data_terms)
            and not any(term in lowered for term in churn_terms)
        )

    def _customer_lookup_sql(self, question: str) -> str:
        city = self._extract_after(question, ("ville de", "ville d'", "a ", "à ", "sur ", "dans "))
        region = self._extract_after(question, ("region de", "région de", "region ", "région "))
        where_clause = ""
        if city:
            where_clause = f"WHERE lower(g.city) = lower('{self._sql_literal(city)}')"
        elif region:
            where_clause = f"WHERE lower(g.region) = lower('{self._sql_literal(region)}')"

        return f"""
            SELECT
              c.customer_id,
              c.first_name,
              c.last_name,
              c.customer_segment,
              c.digital_profile,
              a.agency_name,
              g.city,
              g.region
            FROM {self.config.schema_name}.dim_customer c
            JOIN {self.config.schema_name}.dim_agency a
              ON a.agency_id = c.home_agency_id
            JOIN {self.config.schema_name}.dim_geography g
              ON g.geography_id = c.geography_id
            {where_clause}
            ORDER BY c.customer_id
        """

    @staticmethod
    def _extract_after(question: str, prefixes: tuple[str, ...]) -> str | None:
        lowered = question.lower()
        for prefix in prefixes:
            index = lowered.find(prefix)
            if index == -1:
                continue
            raw = question[index + len(prefix):]
            match = re.match(r"\s*([A-Za-zÀ-ÿ' -]+)", raw)
            if not match:
                continue
            value = match.group(1).strip(" ?.!,;:")
            return value[:60] if value else None
        return None

    @staticmethod
    def _sql_literal(value: str) -> str:
        return value.replace("'", "''")

    def _customer_count_sql(self) -> str:
        return f"""
            SELECT
              count(DISTINCT customer_id) AS total_customers
            FROM {self.config.schema_name}.dim_customer
        """

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
              count(*) AS customers_to_contact,
              round(avg(q.churn_probability)::numeric, 4) AS avg_churn_probability,
              round(avg(CASE WHEN r.human_review_status = 'APPROVED' THEN 1 ELSE 0 END)::numeric, 4)
                AS approved_action_rate
            FROM {self.config.retention_queue_fqn} q
            LEFT JOIN {self.config.retention_recommendation_fqn} r
              ON r.customer_id = q.customer_id
             AND r.observation_date = q.observation_date
             AND r.mlflow_run_id = q.mlflow_run_id
            WHERE q.scored_at >= date_trunc('week', current_date)
            GROUP BY q.agency_name, q.region
            ORDER BY customers_to_contact DESC, avg_churn_probability DESC
        """
