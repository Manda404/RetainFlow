"""Supervisor agent that routes business questions to RetainFlow agents."""

from __future__ import annotations

from retainflow.agents.base import AgentResponse
from retainflow.agents.customer_profile_agent import CustomerProfileAgent
from retainflow.agents.data_visualization_agent import DataVisualizationAgent
from retainflow.agents.email_drafting_agent import EmailDraftingAgent
from retainflow.agents.explainability_agent import ExplainabilityAgent
from retainflow.agents.kpi_agent import KPIAgent
from retainflow.agents.llm_router import LLMRouter
from retainflow.agents.retention_advisor_agent import RetentionAdvisorAgent
from retainflow.agents.sql_agent import SQLAgent
from retainflow.agents.strategy_rag_agent import StrategyRAGAgent
from retainflow.config import ChurnModelConfig


class SupervisorAgent:
    """Coordinate SQL, KPI, retention, explainability, email, and visualization agents."""

    def __init__(
        self,
        config: ChurnModelConfig,
        sql_agent: SQLAgent | None = None,
        kpi_agent: KPIAgent | None = None,
        retention_agent: RetentionAdvisorAgent | None = None,
        explainability_agent: ExplainabilityAgent | None = None,
        visualization_agent: DataVisualizationAgent | None = None,
        email_agent: EmailDraftingAgent | None = None,
        rag_agent: StrategyRAGAgent | None = None,
        customer_profile_agent: CustomerProfileAgent | None = None,
        llm_router: LLMRouter | None = None,
    ) -> None:
        self.config = config
        self.sql_agent = sql_agent or SQLAgent(config)
        self.kpi_agent = kpi_agent or KPIAgent(config)
        self.retention_agent = retention_agent or RetentionAdvisorAgent(config)
        self.explainability_agent = explainability_agent or ExplainabilityAgent(config)
        self.visualization_agent = visualization_agent or DataVisualizationAgent()
        self.email_agent = email_agent or EmailDraftingAgent()
        self.rag_agent = rag_agent or StrategyRAGAgent()
        self.customer_profile_agent = customer_profile_agent or CustomerProfileAgent(config)
        self.llm_router = llm_router or LLMRouter.from_env()

    def answer(self, question: str, limit: int = 5) -> AgentResponse:
        """Route a question to the most useful local workflow."""
        lowered = question.lower()
        customer_id = self._extract_customer_id(question)
        route = self.llm_router.route(question)
        intent = route.intent if route else self._deterministic_intent(lowered, customer_id)

        if intent == "customer_profile" and customer_id is None:
            return AgentResponse(
                agent_name="SupervisorAgent",
                answer="Please provide a customer identifier such as CUST_000123.",
                metadata={
                    "steps": ["SupervisorAgent"],
                    "routing": self._routing_metadata(route, "customer_profile"),
                },
            )

        if customer_id:
            profile = self.customer_profile_agent.by_customer_id(customer_id)
            explanations = self.explainability_agent.global_drivers(top_n=5)
            return AgentResponse(
                agent_name="SupervisorAgent",
                answer=f"{profile.answer} Model context: {explanations.answer}",
                data=profile.data,
                metadata={
                    "steps": ["CustomerProfileAgent", "ExplainabilityAgent"],
                    "routing": self._routing_metadata(route, "customer_profile"),
                    "profile_sql": profile.metadata.get("sql"),
                    "shap_artifact": explanations.metadata.get("artifact"),
                },
            )

        if intent == "visualization":
            sql_response = self.sql_agent.answer(question, limit=max(limit, 20))
            visual_response = self.visualization_agent.answer(question, sql_response.data)
            return AgentResponse(
                agent_name="SupervisorAgent",
                answer=(
                    "I executed a read-only SQL query and generated a visual. "
                    f"{visual_response.answer}"
                ),
                data=visual_response.data,
                metadata={
                    "steps": ["SQLAgent", "DataVisualizationAgent"],
                    "routing": self._routing_metadata(route, "visualization"),
                    "sql": sql_response.metadata.get("sql"),
                    "visualization": visual_response.metadata,
                },
            )

        if intent == "email":
            recommendations = self.retention_agent.top_recommendations(limit=limit)
            draft = self.email_agent.draft_first(recommendations.data)
            return AgentResponse(
                agent_name="SupervisorAgent",
                answer=draft.answer,
                data=draft.data,
                metadata={
                    "steps": ["RetentionAdvisorAgent", "EmailDraftingAgent"],
                    "routing": self._routing_metadata(route, "email"),
                    "recommendation_sql": recommendations.metadata.get("sql"),
                },
            )

        if intent == "kpi":
            response = self.kpi_agent.answer(question)
            response.metadata["routing"] = self._routing_metadata(route, "kpi")
            return response

        priority = self.retention_agent.top_clients(limit=limit)
        explanations = self.explainability_agent.global_drivers(top_n=5)
        strategy = self.rag_agent.search(question, limit=3) if intent == "strategy" else None
        steps = ["RetentionAdvisorAgent", "ExplainabilityAgent"]
        answer = f"{priority.answer} Global model explanation: {explanations.answer}"
        metadata = {
            "steps": steps,
            "routing": self._routing_metadata(route, intent),
            "priority_sql": priority.metadata.get("sql"),
            "shap_artifact": explanations.metadata.get("artifact"),
        }
        if strategy is not None:
            steps.append("StrategyRAGAgent")
            answer = f"{answer} Marketing strategy: {strategy.answer}"
            metadata["strategy_rag"] = strategy.metadata
        return AgentResponse(
            agent_name="SupervisorAgent",
            answer=answer,
            data=priority.data,
            metadata=metadata,
        )

    @staticmethod
    def _extract_customer_id(question: str) -> str | None:
        """Extract a RetainFlow customer identifier from a natural-language question."""
        import re

        match = re.search(r"\bCUST[_-]\d+\b", question, flags=re.IGNORECASE)
        return match.group(0).replace("-", "_").upper() if match else None

    @staticmethod
    def _deterministic_intent(lowered_question: str, customer_id: str | None = None) -> str:
        """Fallback route when the optional LLM supervisor is unavailable."""
        if customer_id:
            return "customer_profile"
        if any(
            word in lowered_question
            for word in ("chart", "graph", "plot", "visual", "visualize", "visualise", "visuel")
        ):
            return "visualization"
        if any(word in lowered_question for word in ("email", "mail", "message", "draft")):
            return "email"
        if any(
            word in lowered_question
            for word in (
                "kpi",
                "metric",
                "metrics",
                "rate",
                "taux",
                "volume",
                "distribution",
                "repartition",
            )
        ):
            return "kpi"
        if any(
            word in lowered_question
            for word in (
                "strategie",
                "stratégie",
                "marketing",
                "campagne",
                "cible",
                "offre",
                "strategy",
                "campaign",
                "target",
                "offer",
                "price-sensitive",
            )
        ):
            return "strategy"
        return "retention"

    @staticmethod
    def _routing_metadata(route, fallback_intent: str) -> dict[str, object]:
        """Expose whether routing came from the LLM supervisor or fallback logic."""
        if route is None:
            return {"mode": "deterministic_fallback", "intent": fallback_intent}
        return {
            "mode": "llm",
            "intent": route.intent,
            "confidence": route.confidence,
            "reason": route.reason,
        }
