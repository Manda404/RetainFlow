"""Supervisor agent that routes business questions to RetainFlow agents."""

from __future__ import annotations

from retainflow.agents.base import AgentResponse
from retainflow.agents.customer_profile_agent import CustomerProfileAgent
from retainflow.agents.data_visualization_agent import DataVisualizationAgent
from retainflow.agents.email_drafting_agent import EmailDraftingAgent
from retainflow.agents.explainability_agent import ExplainabilityAgent
from retainflow.agents.kpi_agent import KPIAgent
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

    def answer(self, question: str, limit: int = 5) -> AgentResponse:
        """Route a question to the most useful local workflow."""
        lowered = question.lower()
        wants_visual = any(word in lowered for word in ("graph", "plot", "visuel", "visualise"))
        wants_email = any(word in lowered for word in ("email", "mail", "message"))
        wants_kpi = any(word in lowered for word in ("kpi", "taux", "volume", "repartition"))
        wants_strategy = any(
            word in lowered
            for word in ("strategie", "stratégie", "marketing", "campagne", "cible", "offre")
        )
        customer_id = self._extract_customer_id(question)

        if customer_id:
            profile = self.customer_profile_agent.by_customer_id(customer_id)
            explanations = self.explainability_agent.global_drivers(top_n=5)
            return AgentResponse(
                agent_name="SupervisorAgent",
                answer=f"{profile.answer} Contexte modele: {explanations.answer}",
                data=profile.data,
                metadata={
                    "steps": ["CustomerProfileAgent", "ExplainabilityAgent"],
                    "profile_sql": profile.metadata.get("sql"),
                    "shap_artifact": explanations.metadata.get("artifact"),
                },
            )

        if wants_visual:
            sql_response = self.sql_agent.answer(question, limit=max(limit, 20))
            visual_response = self.visualization_agent.answer(question, sql_response.data)
            return AgentResponse(
                agent_name="SupervisorAgent",
                answer=(
                    "J'ai execute une requete SQL read-only puis genere un visuel. "
                    f"{visual_response.answer}"
                ),
                data=visual_response.data,
                metadata={
                    "steps": ["SQLAgent", "DataVisualizationAgent"],
                    "sql": sql_response.metadata.get("sql"),
                    "visualization": visual_response.metadata,
                },
            )

        if wants_email:
            recommendations = self.retention_agent.top_recommendations(limit=limit)
            draft = self.email_agent.draft_first(recommendations.data)
            return AgentResponse(
                agent_name="SupervisorAgent",
                answer=draft.answer,
                data=draft.data,
                metadata={
                    "steps": ["RetentionAdvisorAgent", "EmailDraftingAgent"],
                    "recommendation_sql": recommendations.metadata.get("sql"),
                },
            )

        if wants_kpi:
            return self.kpi_agent.answer(question)

        priority = self.retention_agent.top_clients(limit=limit)
        explanations = self.explainability_agent.global_drivers(top_n=5)
        strategy = self.rag_agent.search(question, limit=3) if wants_strategy else None
        steps = ["RetentionAdvisorAgent", "ExplainabilityAgent"]
        answer = f"{priority.answer} Explication globale modele: {explanations.answer}"
        metadata = {
            "steps": steps,
            "priority_sql": priority.metadata.get("sql"),
            "shap_artifact": explanations.metadata.get("artifact"),
        }
        if strategy is not None:
            steps.append("StrategyRAGAgent")
            answer = f"{answer} Strategie marketing: {strategy.answer}"
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
