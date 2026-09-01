import pandas as pd
import pytest

from retainflow.agents import DataVisualizationAgent, SupervisorAgent
from retainflow.agents.base import AgentResponse
from retainflow.config import load_churn_model_config
from retainflow.tools.sql_tool import SQLTool
from retainflow.tools.visualization_tool import VisualizationTool


class _FakeSQLTool:
    def query(self, sql: str, params=None, limit: int | None = None):
        from retainflow.tools.sql_tool import SQLQueryResult

        frame = pd.DataFrame(
            {
                "agency_name": ["Agence Paris", "Agence Lyon"],
                "clients_a_contacter": [18, 11],
                "region": ["Ile-de-France", "Auvergne-Rhone-Alpes"],
            }
        )
        return SQLQueryResult(dataframe=frame, sql=sql, row_count=len(frame), truncated=False)


class _FakeRetentionAgent:
    def top_clients(self, limit: int = 5):
        return AgentResponse("RetentionAdvisorAgent", "clients", pd.DataFrame(), {})

    def top_recommendations(self, limit: int = 5):
        return AgentResponse("RetentionAdvisorAgent", "recommendations", pd.DataFrame(), {})


class _FakeExplainabilityAgent:
    def global_drivers(self, top_n: int = 5):
        return AgentResponse("ExplainabilityAgent", "drivers", pd.DataFrame(), {})


class _FakeCustomerProfileAgent:
    def by_customer_id(self, customer_id: str):
        return AgentResponse(
            "CustomerProfileAgent",
            f"profile {customer_id}",
            pd.DataFrame({"customer_id": [customer_id]}),
            {"sql": "SELECT profile"},
        )


def test_sql_tool_rejects_mutation_keywords() -> None:
    sql_tool = SQLTool(load_churn_model_config("config/churn_model.yml"))

    with pytest.raises(ValueError, match="Unsafe SQL keyword"):
        sql_tool.validate_read_only("SELECT * FROM retainflow.dim_customer; DROP TABLE x")


def test_sql_tool_wraps_query_with_limit() -> None:
    sql_tool = SQLTool(load_churn_model_config("config/churn_model.yml"), default_limit=10)

    wrapped = sql_tool._with_limit("SELECT * FROM retainflow.dim_customer", limit=10)

    assert "LIMIT 10" in wrapped
    assert "retainflow_agent_query" in wrapped


def test_visualization_tool_creates_plotly_bar() -> None:
    frame = pd.DataFrame({"region": ["Nord", "Sud"], "clients": [12, 8]})

    result = VisualizationTool().bar(frame, x="region", y="clients")

    assert result.chart_type == "bar"
    assert "Nord" in result.interpretation
    assert result.figure is not None


def test_data_visualization_agent_returns_metadata() -> None:
    frame = pd.DataFrame({"region": ["Nord", "Sud"], "clients": [12, 8]})

    response = DataVisualizationAgent().answer("fais un visuel des clients par region", frame)

    assert response.agent_name == "DataVisualizationAgent"
    assert response.metadata["chart_type"] == "bar"


def test_supervisor_routes_visual_question() -> None:
    from retainflow.agents.sql_agent import SQLAgent

    config = load_churn_model_config("config/churn_model.yml")
    sql_agent = SQLAgent(config, sql_tool=_FakeSQLTool())
    supervisor = SupervisorAgent(
        config,
        sql_agent=sql_agent,
        retention_agent=_FakeRetentionAgent(),
        explainability_agent=_FakeExplainabilityAgent(),
    )

    response = supervisor.answer("visualise les clients contactes cette semaine par agence")

    assert response.agent_name == "SupervisorAgent"
    assert response.metadata["steps"] == ["SQLAgent", "DataVisualizationAgent"]
    assert response.data is not None


def test_supervisor_routes_customer_id_question() -> None:
    config = load_churn_model_config("config/churn_model.yml")
    supervisor = SupervisorAgent(
        config,
        retention_agent=_FakeRetentionAgent(),
        explainability_agent=_FakeExplainabilityAgent(),
        customer_profile_agent=_FakeCustomerProfileAgent(),
    )

    response = supervisor.answer("Pourquoi le client CUST-000123 risque de churner ?")

    assert response.agent_name == "SupervisorAgent"
    assert response.metadata["steps"] == ["CustomerProfileAgent", "ExplainabilityAgent"]
    assert response.data.iloc[0]["customer_id"] == "CUST_000123"
