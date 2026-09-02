import pandas as pd
import pytest

from retainflow.agents import DataVisualizationAgent, SupervisorAgent
from retainflow.agents.base import AgentResponse
from retainflow.agents.llm_reasoning_agent import LLMReasoningResult
from retainflow.agents.llm_router import LLMRouter
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


class _FakeCustomerCountSQLTool:
    def query(self, sql: str, params=None, limit: int | None = None):
        from retainflow.tools.sql_tool import SQLQueryResult

        frame = pd.DataFrame({"total_customers": [10000]})
        return SQLQueryResult(dataframe=frame, sql=sql, row_count=len(frame), truncated=False)


class _FakeCustomerLookupSQLTool:
    def query(self, sql: str, params=None, limit: int | None = None):
        from retainflow.tools.sql_tool import SQLQueryResult

        assert "dim_customer" in sql
        assert "g.city" in sql
        assert "Paris" in sql
        frame = pd.DataFrame(
            {
                "customer_id": ["CUST_000001"],
                "first_name": ["Nadia"],
                "last_name": ["Martin"],
                "city": ["Paris"],
                "region": ["Ile-de-France"],
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


class _FakeKPIAgent:
    def answer(self, question: str):
        return AgentResponse(
            "KPIAgent",
            "kpi",
            pd.DataFrame({"region": ["Ile-de-France"], "clients": [12]}),
            {"kpi": "priority customers by region"},
        )


class _FakeLLMRouter:
    def __init__(self, route=None):
        self._route = route

    def route(self, question: str):
        return self._route


class _FakeLLMReasoningAgent:
    enabled = True
    provider = "test"
    model = "test-model"

    def explain_customer_risk(self, **kwargs):
        return LLMReasoningResult(
            answer="Explication LLM basee sur les preuves controlees.",
            confidence=0.87,
            used_facts=["prediction", "signals", "shap_drivers"],
        )


class _UnavailableLLMReasoningAgent:
    enabled = True
    provider = "test"
    model = "test-model"

    def explain_customer_risk(self, **kwargs):
        return None


class _FakeLLMRoute:
    intent = "kpi"
    reason = "The user is asking for metrics."
    confidence = 0.91


class _FakeRetentionLLMRoute:
    intent = "retention"
    reason = "Incorrectly interpreted as customer ranking."
    confidence = 0.91


class _FakeCustomerProfileAgent:
    def by_customer_id(self, customer_id: str):
        return AgentResponse(
            "CustomerProfileAgent",
            f"profile {customer_id}",
            pd.DataFrame(
                {
                    "customer_id": [customer_id],
                    "churn_probability": [0.63],
                    "churn_risk_band": ["HIGH"],
                    "price_sensitivity_score": [0.82],
                    "avg_satisfaction_score_12m": [2.4],
                    "renewal_days_min": [18],
                    "next_best_step": ["Call the customer before renewal."],
                }
            ),
            {"sql": "SELECT profile", "row_count": 1},
            "customer_profile",
        )


class _FakeRAGAgent:
    def search(self, question: str, limit: int = 5):
        return AgentResponse(
            "StrategyRAGAgent",
            "3 targeted marketing strategies found: Retention Strategy - Price-Sensitive Customers.",
            pd.DataFrame(
                {
                    "document_id": ["strategie_sensibilite_prix"],
                    "title": ["Retention Strategy - Price-Sensitive Customers"],
                    "path": ["data/docs/strategy_marketing/strategie_sensibilite_prix.md"],
                    "score": [0.42],
                    "preview": ["Offer a controlled loyalty discount after checking customer value."],
                }
            ),
            {
                "top_k": limit,
                "retrieval_status": "relevant",
                "corrected": False,
                "activity": [
                    {
                        "id": "step_1",
                        "agent": "StrategyRAGAgent",
                        "tool": "StrategyRAGTool",
                        "business_label": "Retention Knowledge",
                        "status": "completed",
                        "summary": "Retrieved 1 retention strategy documents.",
                        "sources": [
                            {
                                "document_id": "strategie_sensibilite_prix",
                                "title": "Retention Strategy - Price-Sensitive Customers",
                            }
                        ],
                    }
                ],
            },
            "retention_strategy",
        )


class _FakeMissingCustomerProfileAgent:
    def by_customer_id(self, customer_id: str):
        return AgentResponse(
            "CustomerProfileAgent",
            f"No profile found for customer {customer_id}.",
            pd.DataFrame(),
            {"sql": "SELECT profile", "row_count": 0},
            "customer_not_found",
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


def test_sql_agent_rejects_unmapped_questions() -> None:
    from retainflow.agents.sql_agent import SQLAgent

    sql_agent = SQLAgent(load_churn_model_config("config/churn_model.yml"), sql_tool=_FakeSQLTool())

    with pytest.raises(ValueError, match="cannot map this question"):
        sql_agent.build_sql("montre moi quelque chose")


def test_visualization_tool_creates_plotly_bar() -> None:
    frame = pd.DataFrame({"region": ["Nord", "Sud"], "clients": [12, 8]})

    result = VisualizationTool().bar(frame, x="region", y="clients")

    assert result.chart_type == "bar"
    assert "Nord" in result.interpretation
    assert result.figure is not None
    payload = result.figure.to_plotly_json()
    assert payload["data"][0]["orientation"] == "h"
    assert payload["layout"]["xaxis"]["title"]["text"] == "Customers"
    assert payload["layout"]["yaxis"]["title"]["text"] == "Region"


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
        llm_router=_FakeLLMRouter(),
    )

    response = supervisor.answer("visualise les clients contactes cette semaine par agence")

    assert response.agent_name == "SupervisorAgent"
    assert response.metadata["steps"] == ["SQLAgent", "DataVisualizationAgent"]
    assert response.business_type == "visualization"
    assert [item["agent"] for item in response.metadata["activity"]] == [
        "SupervisorAgent",
        "SQLAgent",
        "DataVisualizationAgent",
    ]
    assert response.data is not None


def test_supervisor_routes_english_visual_question() -> None:
    from retainflow.agents.sql_agent import SQLAgent

    config = load_churn_model_config("config/churn_model.yml")
    sql_agent = SQLAgent(config, sql_tool=_FakeSQLTool())
    supervisor = SupervisorAgent(
        config,
        sql_agent=sql_agent,
        retention_agent=_FakeRetentionAgent(),
        explainability_agent=_FakeExplainabilityAgent(),
        llm_router=_FakeLLMRouter(),
    )

    response = supervisor.answer("Visualize priority customers by region")

    assert response.agent_name == "SupervisorAgent"
    assert response.metadata["steps"] == ["SQLAgent", "DataVisualizationAgent"]
    assert response.data is not None


def test_supervisor_routes_english_kpi_question() -> None:
    config = load_churn_model_config("config/churn_model.yml")
    supervisor = SupervisorAgent(
        config,
        kpi_agent=_FakeKPIAgent(),
        retention_agent=_FakeRetentionAgent(),
        explainability_agent=_FakeExplainabilityAgent(),
        llm_router=_FakeLLMRouter(),
    )

    response = supervisor.answer("Show me KPI metrics by region")

    assert response.agent_name == "KPIAgent"
    assert response.business_type == "kpi"
    assert response.metadata["kpi"] == "priority customers by region"
    assert [item["agent"] for item in response.metadata["activity"]] == [
        "SupervisorAgent",
        "KPIAgent",
    ]


def test_supervisor_routes_customer_data_count_to_sql_agent() -> None:
    from retainflow.agents.sql_agent import SQLAgent

    config = load_churn_model_config("config/churn_model.yml")
    sql_agent = SQLAgent(config, sql_tool=_FakeCustomerCountSQLTool())
    supervisor = SupervisorAgent(
        config,
        sql_agent=sql_agent,
        retention_agent=_FakeRetentionAgent(),
        explainability_agent=_FakeExplainabilityAgent(),
        llm_router=_FakeLLMRouter(),
        llm_reasoning_agent=_UnavailableLLMReasoningAgent(),
    )

    response = supervisor.answer("combien de donnée client j'ai dans ma base de donnée ?")

    assert response.business_type == "data_count"
    assert response.answer == "La base contient 10 000 clients uniques."
    assert response.metadata["steps"] == ["SQLAgent"]
    assert response.data.iloc[0]["total_customers"] == 10000
    assert [item["agent"] for item in response.metadata["activity"]] == [
        "SupervisorAgent",
        "SQLAgent",
    ]


def test_supervisor_routes_customer_city_lookup_to_data_query() -> None:
    from retainflow.agents.sql_agent import SQLAgent

    config = load_churn_model_config("config/churn_model.yml")
    sql_agent = SQLAgent(config, sql_tool=_FakeCustomerLookupSQLTool())
    supervisor = SupervisorAgent(
        config,
        sql_agent=sql_agent,
        retention_agent=_FakeRetentionAgent(),
        explainability_agent=_FakeExplainabilityAgent(),
        llm_router=_FakeLLMRouter(),
        llm_reasoning_agent=_UnavailableLLMReasoningAgent(),
    )

    response = supervisor.answer("quel sont les client que j'ai dans la ville de Paris ?")

    assert response.business_type == "data_query"
    assert response.metadata["routing"]["intent"] == "data_query"
    assert response.metadata["steps"] == ["SQLAgent"]
    assert response.data.iloc[0]["city"] == "Paris"
    assert [item["agent"] for item in response.metadata["activity"]] == [
        "SupervisorAgent",
        "SQLAgent",
    ]


def test_supervisor_uses_llm_route_when_available() -> None:
    config = load_churn_model_config("config/churn_model.yml")
    supervisor = SupervisorAgent(
        config,
        kpi_agent=_FakeKPIAgent(),
        retention_agent=_FakeRetentionAgent(),
        explainability_agent=_FakeExplainabilityAgent(),
        llm_router=_FakeLLMRouter(_FakeLLMRoute()),
    )

    response = supervisor.answer("What should I inspect?")

    assert response.agent_name == "KPIAgent"
    assert response.metadata["routing"]["mode"] == "llm"
    assert response.metadata["routing"]["intent"] == "kpi"


def test_supervisor_priority_question_does_not_add_global_explanation() -> None:
    config = load_churn_model_config("config/churn_model.yml")
    supervisor = SupervisorAgent(
        config,
        retention_agent=_FakeRetentionAgent(),
        explainability_agent=_FakeExplainabilityAgent(),
        llm_router=_FakeLLMRouter(),
    )

    response = supervisor.answer("Quels clients faut-il traiter en priorite ?")

    assert response.business_type == "customer_ranking"
    assert response.answer == "clients"
    assert "Global model" not in response.answer
    assert response.metadata["steps"] == ["RetentionAdvisorAgent"]
    assert [item["agent"] for item in response.metadata["activity"]] == [
        "SupervisorAgent",
        "RetentionAdvisorAgent",
    ]


def test_supervisor_does_not_guess_when_question_is_unsupported() -> None:
    config = load_churn_model_config("config/churn_model.yml")
    supervisor = SupervisorAgent(
        config,
        retention_agent=_FakeRetentionAgent(),
        explainability_agent=_FakeExplainabilityAgent(),
        llm_router=_FakeLLMRouter(),
        llm_reasoning_agent=_UnavailableLLMReasoningAgent(),
    )

    response = supervisor.answer("peux tu analyser les contrats fournisseurs ?")

    assert response.business_type == "text"
    assert response.metadata["routing"]["intent"] == "unsupported"
    assert response.metadata["steps"] == ["SupervisorAgent"]
    assert "Je ne peux pas traiter cette demande" in response.answer
    assert [item["agent"] for item in response.metadata["activity"]] == [
        "SupervisorAgent",
        "SupervisorAgent",
    ]


def test_llm_router_parses_supported_intent() -> None:
    router = LLMRouter(
        enabled=True,
        provider="groq",
        model="llama-3.3-70b-versatile",
        api_key="test-key",
    )

    route = router._parse_route(
        '{"intent": "visualization", "reason": "The user asks for a chart.", "confidence": 0.88}'
    )

    assert route is not None
    assert route.intent == "visualization"
    assert route.confidence == 0.88


def test_supervisor_routes_customer_id_question() -> None:
    config = load_churn_model_config("config/churn_model.yml")
    supervisor = SupervisorAgent(
        config,
        retention_agent=_FakeRetentionAgent(),
        explainability_agent=_FakeExplainabilityAgent(),
        customer_profile_agent=_FakeCustomerProfileAgent(),
        llm_router=_FakeLLMRouter(),
        llm_reasoning_agent=_UnavailableLLMReasoningAgent(),
    )

    response = supervisor.answer("Pourquoi le client CUST-000123 risque de churner ?")

    assert response.agent_name == "SupervisorAgent"
    assert response.business_type == "risk_explanation"
    assert "le modele estime une probabilite de churn de 63%" in response.answer
    assert "Top global model drivers" not in response.answer
    assert response.metadata["steps"] == [
        "CustomerProfileAgent",
        "ExplainabilityAgent",
        "ReasoningOrchestrator",
    ]
    assert response.metadata["model_context"] == "drivers"
    assert response.metadata["reasoning"]["goal"] == "explain_customer_churn"
    assert response.metadata["llm_reasoning"]["used"] is False
    assert [item["agent"] for item in response.metadata["activity"]] == [
        "SupervisorAgent",
        "CustomerProfileAgent",
        "ExplainabilityAgent",
        "ReasoningOrchestrator",
        "LLMReasoningAgent",
    ]
    assert response.metadata["activity"][2]["details"]["scope"] == "global"
    assert response.metadata["activity"][3]["details"]["signals"] >= 1
    assert response.metadata["activity"][4]["status"] == "skipped"
    assert response.data.iloc[0]["customer_id"] == "CUST_000123"


def test_supervisor_uses_llm_reasoning_when_available() -> None:
    config = load_churn_model_config("config/churn_model.yml")
    supervisor = SupervisorAgent(
        config,
        retention_agent=_FakeRetentionAgent(),
        explainability_agent=_FakeExplainabilityAgent(),
        customer_profile_agent=_FakeCustomerProfileAgent(),
        llm_router=_FakeLLMRouter(),
        llm_reasoning_agent=_FakeLLMReasoningAgent(),
    )

    response = supervisor.answer("Pourquoi le client CUST-000123 risque de churner ?")

    assert response.answer == "Explication LLM basee sur les preuves controlees."
    assert response.metadata["steps"] == [
        "CustomerProfileAgent",
        "ExplainabilityAgent",
        "ReasoningOrchestrator",
        "LLMReasoningAgent",
    ]
    assert response.metadata["llm_reasoning"]["used"] is True
    assert response.metadata["llm_reasoning"]["confidence"] == 0.87
    assert response.metadata["activity"][4]["status"] == "completed"


def test_supervisor_customer_not_found_skips_downstream_agents() -> None:
    config = load_churn_model_config("config/churn_model.yml")
    supervisor = SupervisorAgent(
        config,
        retention_agent=_FakeRetentionAgent(),
        explainability_agent=_FakeExplainabilityAgent(),
        customer_profile_agent=_FakeMissingCustomerProfileAgent(),
        llm_router=_FakeLLMRouter(),
        llm_reasoning_agent=_UnavailableLLMReasoningAgent(),
    )

    response = supervisor.answer("Why is CUST_999999 at risk?")

    assert response.business_type == "customer_not_found"
    assert "Customer not found" in response.answer
    assert response.metadata["steps"] == ["CustomerProfileAgent"]
    assert [item["agent"] for item in response.metadata["activity"]] == [
        "SupervisorAgent",
        "CustomerProfileAgent",
        "ExplainabilityAgent",
        "StrategyRAGAgent",
    ]
    assert response.metadata["activity"][2]["status"] == "skipped"
    assert response.metadata["activity"][3]["status"] == "skipped"


def test_supervisor_routes_price_sensitive_strategy_to_rag_only() -> None:
    config = load_churn_model_config("config/churn_model.yml")
    supervisor = SupervisorAgent(
        config,
        retention_agent=_FakeRetentionAgent(),
        explainability_agent=_FakeExplainabilityAgent(),
        rag_agent=_FakeRAGAgent(),
        llm_router=_FakeLLMRouter(),
    )

    response = supervisor.answer(
        "Quels leviers de retention utiliser pour les clients sensibles au prix ?"
    )

    assert response.business_type == "retention_strategy"
    assert response.metadata["steps"] == ["StrategyRAGAgent"]
    assert [item["agent"] for item in response.metadata["activity"]] == [
        "SupervisorAgent",
        "StrategyRAGAgent",
    ]
    assert "Price-Sensitive Customers" in response.answer


def test_supervisor_overrides_llm_when_strategy_wording_is_explicit() -> None:
    config = load_churn_model_config("config/churn_model.yml")
    supervisor = SupervisorAgent(
        config,
        retention_agent=_FakeRetentionAgent(),
        explainability_agent=_FakeExplainabilityAgent(),
        rag_agent=_FakeRAGAgent(),
        llm_router=_FakeLLMRouter(_FakeRetentionLLMRoute()),
    )

    response = supervisor.answer(
        "Quels leviers de retention utiliser pour les clients sensibles au prix ?"
    )

    assert response.business_type == "retention_strategy"
    assert response.metadata["routing"]["mode"] == "deterministic_override"
    assert response.metadata["routing"]["llm_intent"] == "retention"
    assert [item["agent"] for item in response.metadata["activity"]] == [
        "SupervisorAgent",
        "StrategyRAGAgent",
    ]
