"""Supervisor agent that routes business questions to RetainFlow agents."""

from __future__ import annotations

import pandas as pd

from retainflow.agents.activity import activity_item, routing_activity
from retainflow.agents.base import AgentResponse
from retainflow.agents.customer_profile_agent import CustomerProfileAgent
from retainflow.agents.data_visualization_agent import DataVisualizationAgent
from retainflow.agents.email_drafting_agent import EmailDraftingAgent
from retainflow.agents.explainability_agent import ExplainabilityAgent
from retainflow.agents.kpi_agent import KPIAgent
from retainflow.agents.llm_reasoning_agent import LLMReasoningAgent
from retainflow.agents.llm_router import LLMRouter
from retainflow.agents.reasoning_orchestrator import ReasoningOrchestrator
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
        reasoning_orchestrator: ReasoningOrchestrator | None = None,
        llm_reasoning_agent: LLMReasoningAgent | None = None,
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
        self.reasoning_orchestrator = reasoning_orchestrator or ReasoningOrchestrator()
        self.llm_reasoning_agent = llm_reasoning_agent or LLMReasoningAgent.from_env()

    def answer(self, question: str, limit: int = 5) -> AgentResponse:
        """Route a question to the most useful local workflow."""
        lowered = question.lower()
        customer_id = self._extract_customer_id(question)
        route = self.llm_router.route(question)
        deterministic_intent = self._deterministic_intent(lowered, customer_id)
        intent = route.intent if route else deterministic_intent
        routing = self._routing_metadata(route, intent)
        if route is not None and deterministic_intent in {"strategy", "data_count", "data_query"} and route.intent != deterministic_intent:
            intent = deterministic_intent
            routing = {
                "mode": "deterministic_override",
                "intent": intent,
                "llm_intent": route.intent,
                "reason": "Business wording explicitly maps to a protected deterministic workflow.",
            }
        activity = [
            routing_activity(
                "step_1",
                intent=str(routing["intent"]),
                mode=str(routing["mode"]),
            )
        ]

        if intent == "customer_profile" and customer_id is None:
            return AgentResponse(
                agent_name="SupervisorAgent",
                answer="Please provide a customer identifier such as CUST_000123.",
                metadata={
                    "steps": ["SupervisorAgent"],
                    "routing": routing,
                    "activity": activity,
                },
                business_type="text",
            )

        if intent == "unsupported":
            activity.append(
                activity_item(
                    id="step_2",
                    agent="SupervisorAgent",
                    business_label="Capability Check",
                    status="skipped",
                    summary="No safe RetainFlow workflow matched the request.",
                    details={
                        "supported_intents": [
                            "customer_profile",
                            "retention",
                            "strategy",
                            "kpi",
                            "visualization",
                            "email",
                            "data_count",
                        ]
                    },
                )
            )
            return AgentResponse(
                agent_name="SupervisorAgent",
                answer=(
                    "Je ne peux pas traiter cette demande avec les capacites RetainFlow disponibles. "
                    "Je peux repondre sur les clients a risque, un profil client CUST_..., les strategies "
                    "de retention, les KPI, les visualisations, les emails de retention ou certains comptages en base."
                ),
                metadata={
                    "steps": ["SupervisorAgent"],
                    "routing": routing,
                    "activity": activity,
                },
                business_type="text",
            )

        if intent == "data_count":
            sql_response = self.sql_agent.answer(question, limit=1)
            activity.append(
                activity_item(
                    id="step_2",
                    agent="SQLAgent",
                    tool="SQLTool",
                    business_label="Database Count",
                    status="completed",
                    summary=sql_response.answer,
                    details={
                        "rows": sql_response.metadata.get("row_count", 0),
                        "sql": sql_response.metadata.get("sql"),
                    },
                )
            )
            return AgentResponse(
                agent_name="SupervisorAgent",
                answer=sql_response.answer,
                data=sql_response.data,
                metadata={
                    "steps": ["SQLAgent"],
                    "routing": routing,
                    "sql": sql_response.metadata.get("sql"),
                    "activity": activity,
                },
                business_type=sql_response.business_type,
            )

        if intent == "data_query":
            sql_response = self.sql_agent.answer(question, limit=limit)
            activity.append(
                activity_item(
                    id="step_2",
                    agent="SQLAgent",
                    tool="SQLTool",
                    business_label="Customer Data Query",
                    status="completed",
                    summary=sql_response.answer,
                    details={
                        "rows": sql_response.metadata.get("row_count", 0),
                        "sql": sql_response.metadata.get("sql"),
                    },
                )
            )
            return AgentResponse(
                agent_name="SupervisorAgent",
                answer=sql_response.answer,
                data=sql_response.data,
                metadata={
                    "steps": ["SQLAgent"],
                    "routing": routing,
                    "sql": sql_response.metadata.get("sql"),
                    "activity": activity,
                },
                business_type=sql_response.business_type,
            )

        if customer_id:
            profile = self.customer_profile_agent.by_customer_id(customer_id)
            activity.append(
                activity_item(
                    id="step_2",
                    agent="CustomerProfileAgent",
                    tool="CustomerProfileTool",
                    business_label="Customer Data",
                    status="completed",
                    summary=(
                        f"Customer profile retrieved for {customer_id}."
                        if not self._is_empty_dataframe(profile.data)
                        else f"Customer {customer_id} was not found."
                    ),
                    details={
                        "rows": profile.metadata.get("row_count", 0),
                        "sql": profile.metadata.get("sql"),
                    },
                )
            )
            if self._is_empty_dataframe(profile.data):
                activity.extend(
                    [
                        activity_item(
                            id="step_3",
                            agent="ExplainabilityAgent",
                            tool="ExplainabilityTool",
                            business_label="Risk Explanation",
                            status="skipped",
                            summary="Skipped because no customer profile was found.",
                        ),
                        activity_item(
                            id="step_4",
                            agent="StrategyRAGAgent",
                            tool="StrategyRAGTool",
                            business_label="Retention Knowledge",
                            status="skipped",
                            summary="Skipped because no customer profile was found.",
                        ),
                    ]
                )
                return AgentResponse(
                    agent_name="SupervisorAgent",
                    answer=(
                        f"Customer not found: {customer_id}. "
                        "Please verify the identifier or search for another customer."
                    ),
                    data=profile.data,
                    metadata={
                        "steps": ["CustomerProfileAgent"],
                        "routing": routing,
                        "profile_sql": profile.metadata.get("sql"),
                        "activity": activity,
                    },
                    business_type="customer_not_found",
                )

            explanations = self.explainability_agent.global_drivers(top_n=5)
            reasoning = self.reasoning_orchestrator.explain_customer_risk(
                customer_id=customer_id,
                profile=profile.data,
                shap_summary=explanations.data if isinstance(explanations.data, pd.DataFrame) else None,
            )
            llm_reasoning = self.llm_reasoning_agent.explain_customer_risk(
                question=question,
                customer_id=customer_id,
                deterministic_answer=reasoning.answer,
                reasoning=reasoning.metadata,
            )
            activity.append(
                activity_item(
                    id="step_3",
                    agent="ExplainabilityAgent",
                    tool="ExplainabilityTool",
                    business_label="Global Risk Explanation",
                    status="completed",
                    summary=(
                        "Loaded global SHAP context. Customer-specific SHAP is not available."
                    ),
                    details={"scope": "global", "top_n": explanations.metadata.get("top_n")},
                    sources=[{"type": "artifact", "path": explanations.metadata.get("artifact")}],
                )
            )
            activity.append(
                activity_item(
                    id="step_4",
                    agent="ReasoningOrchestrator",
                    business_label="Customer Risk Reasoning",
                    status="completed",
                    summary="Combined prediction, customer signals and SHAP context into a business explanation.",
                    details={
                        "goal": reasoning.metadata.get("goal"),
                        "signals": len(reasoning.metadata.get("signals", [])),
                        "shap_drivers": len(reasoning.metadata.get("shap_drivers", [])),
                    },
                )
            )
            activity.append(
                activity_item(
                    id="step_5",
                    agent="LLMReasoningAgent",
                    business_label="Final Explanation Drafting",
                    status="completed" if llm_reasoning else "skipped",
                    summary=(
                        "LLM wrote the final customer explanation from verified evidence."
                        if llm_reasoning
                        else "LLM unavailable; deterministic explanation was used."
                    ),
                    details={
                        "provider": self.llm_reasoning_agent.provider,
                        "model": self.llm_reasoning_agent.model,
                        "confidence": llm_reasoning.confidence if llm_reasoning else None,
                        "used_facts": llm_reasoning.used_facts if llm_reasoning else [],
                    },
                )
            )
            steps = ["CustomerProfileAgent", "ExplainabilityAgent", "ReasoningOrchestrator"]
            if llm_reasoning:
                steps.append("LLMReasoningAgent")
            return AgentResponse(
                agent_name="SupervisorAgent",
                answer=llm_reasoning.answer if llm_reasoning else reasoning.answer,
                data=profile.data,
                metadata={
                    "steps": steps,
                    "routing": routing,
                    "profile_sql": profile.metadata.get("sql"),
                    "shap_artifact": explanations.metadata.get("artifact"),
                    "model_context": explanations.answer,
                    "reasoning": reasoning.metadata,
                    "llm_reasoning": {
                        "enabled": self.llm_reasoning_agent.enabled,
                        "used": llm_reasoning is not None,
                        "provider": self.llm_reasoning_agent.provider,
                        "model": self.llm_reasoning_agent.model,
                        "confidence": llm_reasoning.confidence if llm_reasoning else None,
                        "used_facts": llm_reasoning.used_facts if llm_reasoning else [],
                    },
                    "activity": activity,
                },
                business_type="risk_explanation",
            )

        if intent == "visualization":
            sql_response = self.sql_agent.answer(question, limit=max(limit, 20))
            visual_response = self.visualization_agent.answer(question, sql_response.data)
            activity.extend(
                [
                    activity_item(
                        id="step_2",
                        agent="SQLAgent",
                        tool="SQLTool",
                        business_label="Customer Data",
                        status="completed",
                        summary=(
                            f"Retrieved {sql_response.metadata.get('row_count', 0)} rows for visualization."
                        ),
                        details={
                            "rows": sql_response.metadata.get("row_count", 0),
                            "sql": sql_response.metadata.get("sql"),
                        },
                    ),
                    activity_item(
                        id="step_3",
                        agent="DataVisualizationAgent",
                        tool="VisualizationTool",
                        business_label="Business Visualization",
                        status="completed",
                        summary="Generated a business chart from query results.",
                        details={
                            "chart_type": visual_response.metadata.get("chart_type"),
                            "title": visual_response.metadata.get("title"),
                        },
                    ),
                ]
            )
            return AgentResponse(
                agent_name="SupervisorAgent",
                answer=(
                    "I executed a read-only SQL query and generated a visual. "
                    f"{visual_response.answer}"
                ),
                data=visual_response.data,
                metadata={
                    "steps": ["SQLAgent", "DataVisualizationAgent"],
                    "routing": routing,
                    "sql": sql_response.metadata.get("sql"),
                    "visualization": visual_response.metadata,
                    "activity": activity,
                },
                business_type="visualization",
            )

        if intent == "email":
            recommendations = self.retention_agent.top_recommendations(limit=limit)
            draft = self.email_agent.draft_first(recommendations.data)
            activity.extend(
                [
                    activity_item(
                        id="step_2",
                        agent="RetentionAdvisorAgent",
                        tool="RetentionTool",
                        business_label="Retention Recommendations",
                        status="completed",
                        summary=(
                            f"Retrieved {recommendations.metadata.get('row_count', 0)} recommendations."
                        ),
                        details={
                            "rows": recommendations.metadata.get("row_count", 0),
                            "sql": recommendations.metadata.get("sql"),
                        },
                    ),
                    activity_item(
                        id="step_3",
                        agent="EmailDraftingAgent",
                        tool="EmailDraftingTool",
                        business_label="Email Generation",
                        status="completed" if draft.data is not None else "skipped",
                        summary=draft.answer,
                        details={
                            "recipients": 1 if draft.data is not None else 0,
                            "channel": draft.metadata.get("channel"),
                        },
                    ),
                ]
            )
            return AgentResponse(
                agent_name="SupervisorAgent",
                answer=draft.answer,
                data=draft.data,
                metadata={
                    "steps": ["RetentionAdvisorAgent", "EmailDraftingAgent"],
                    "routing": routing,
                    "recommendation_sql": recommendations.metadata.get("sql"),
                    "activity": activity,
                },
                business_type="email_draft",
            )

        if intent == "kpi":
            response = self.kpi_agent.answer(question)
            response.metadata["routing"] = routing
            response.metadata["activity"] = activity + [
                activity_item(
                    id="step_2",
                    agent="KPIAgent",
                    tool="KPITool",
                    business_label="Business KPI",
                    status="completed",
                    summary=f"Computed KPI: {response.metadata.get('kpi', 'business metric')}.",
                    details={
                        "rows": response.metadata.get("row_count", 0),
                        "kpi": response.metadata.get("kpi"),
                        "sql": response.metadata.get("sql"),
                    },
                )
            ]
            return AgentResponse(
                agent_name=response.agent_name,
                answer=response.answer,
                data=response.data,
                metadata=response.metadata,
                business_type="kpi",
            )

        if intent == "strategy":
            strategy = self.rag_agent.search(question, limit=3)
            strategy_activity = strategy.metadata.get("activity", [])
            rag_sources = strategy_activity[0].get("sources") if strategy_activity else None
            activity.append(
                activity_item(
                    id="step_2",
                    agent="StrategyRAGAgent",
                    tool="StrategyRAGTool",
                    business_label="Retention Knowledge",
                    status="completed",
                    summary=f"Retrieved {strategy.metadata.get('top_k', 0)} strategy candidates.",
                    details={
                        "top_k": strategy.metadata.get("top_k"),
                        "retrieval_status": strategy.metadata.get("retrieval_status"),
                        "corrected": strategy.metadata.get("corrected"),
                    },
                    sources=rag_sources,
                )
            )
            return AgentResponse(
                agent_name="SupervisorAgent",
                answer=strategy.answer,
                data=strategy.data,
                metadata={
                    "steps": ["StrategyRAGAgent"],
                    "routing": routing,
                    "strategy_rag": strategy.metadata,
                    "activity": activity,
                },
                business_type="retention_strategy",
            )

        priority = self.retention_agent.top_clients(limit=limit)
        steps = ["RetentionAdvisorAgent"]
        answer = priority.answer
        activity.extend(
            [
                activity_item(
                    id="step_2",
                    agent="RetentionAdvisorAgent",
                    tool="RetentionTool",
                    business_label="Priority Customers",
                    status="completed",
                    summary=f"Retrieved {priority.metadata.get('row_count', 0)} priority customers.",
                    details={
                        "rows": priority.metadata.get("row_count", 0),
                        "sql": priority.metadata.get("sql"),
                    },
                )
            ]
        )
        metadata = {
            "steps": steps,
            "routing": routing,
            "priority_sql": priority.metadata.get("sql"),
            "activity": activity,
        }
        return AgentResponse(
            agent_name="SupervisorAgent",
            answer=answer,
            data=priority.data,
            metadata=metadata,
            business_type="customer_ranking",
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
        if SupervisorAgent._asks_for_data_count(lowered_question):
            return "data_count"
        if SupervisorAgent._asks_for_data_query(lowered_question):
            return "data_query"
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
                "prix",
                "tarif",
                "remise",
                "levier",
                "leviers",
                "sensible au prix",
                "sensibles au prix",
            )
        ):
            return "strategy"
        if SupervisorAgent._asks_for_retention_ranking(lowered_question):
            return "retention"
        return "unsupported"

    @staticmethod
    def _asks_for_data_count(lowered_question: str) -> bool:
        count_terms = ("combien", "nombre", "count", "volume", "total")
        customer_terms = ("client", "clients", "customer", "customers", "donnee client", "donnée client")
        database_terms = ("base", "database", "table", "donnee", "donnée")
        return (
            any(term in lowered_question for term in count_terms)
            and any(term in lowered_question for term in customer_terms)
            and any(term in lowered_question for term in database_terms)
        )

    @staticmethod
    def _asks_for_data_query(lowered_question: str) -> bool:
        customer_terms = ("client", "clients", "customer", "customers")
        data_terms = ("quel", "quels", "liste", "lister", "montre", "affiche", "trouve", "cherche", "ville", "region", "région", "agence")
        churn_terms = ("churn", "risque", "priorite", "priorité", "susceptible", "retention", "rétention")
        return (
            any(term in lowered_question for term in customer_terms)
            and any(term in lowered_question for term in data_terms)
            and not any(term in lowered_question for term in churn_terms)
        )

    @staticmethod
    def _asks_for_retention_ranking(lowered_question: str) -> bool:
        ranking_terms = (
            "priorite",
            "priorité",
            "prioritaires",
            "susceptibles",
            "a risque",
            "à risque",
            "risque de churn",
            "churn",
            "attrition",
            "traiter",
            "contacter",
        )
        customer_terms = ("client", "clients", "customer", "customers", "assure", "assuré", "assures", "assurés")
        return any(term in lowered_question for term in ranking_terms) and any(
            term in lowered_question for term in customer_terms
        )

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

    @staticmethod
    def _is_empty_dataframe(value) -> bool:
        return isinstance(value, pd.DataFrame) and value.empty
