from pathlib import Path

from retainflow.agents import StrategyRAGAgent, SupervisorAgent
from retainflow.config import load_churn_model_config
from retainflow.rag import StrategyDocumentLoader, StrategyRetriever


def test_strategy_document_loader_reads_marketing_docs() -> None:
    documents = StrategyDocumentLoader("data/docs/strategy_marketing").load()

    titles = {document.title for document in documents}

    assert "Strategie Retention - Clients Sensibles Au Prix" in titles
    assert "Strategie Retention - Insatisfaction Service" in titles


def test_strategy_retriever_finds_price_sensitivity_strategy() -> None:
    results = StrategyRetriever("data/docs/strategy_marketing").search(
        "client sensible au prix avec hausse de prime et devis concurrent",
        top_k=2,
    )

    assert results
    assert results[0].document_id == "strategie_sensibilite_prix"
    assert results[0].score > 0
    assert Path(results[0].path).exists()


def test_corrective_retriever_enriches_weak_payment_query() -> None:
    result = StrategyRetriever("data/docs/strategy_marketing").corrective_search(
        "client avec prelevements rejetes et budget fragile",
        top_k=3,
    )

    assert result.results
    assert result.status in {"relevant", "corrected"}
    assert result.results[0].document_id == "strategie_incidents_paiement"


def test_corrective_retriever_finds_claim_strategy() -> None:
    result = StrategyRetriever("data/docs/strategy_marketing").corrective_search(
        "customer unhappy after claim settlement delay",
        top_k=3,
    )

    assert result.results
    assert result.results[0].document_id == "strategie_sinistre_recent"


def test_strategy_rag_agent_returns_dataframe() -> None:
    response = StrategyRAGAgent("data/docs/strategy_marketing").search(
        "strategie marketing pour incidents de paiement",
        limit=3,
    )

    assert response.agent_name == "StrategyRAGAgent"
    assert not response.data.empty
    assert "title" in response.data.columns
    assert response.metadata["retrieval_status"] in {"relevant", "corrected"}


def test_supervisor_routes_strategy_question_to_rag() -> None:
    config = load_churn_model_config("config/churn_model.yml")
    supervisor = SupervisorAgent(config, rag_agent=StrategyRAGAgent("data/docs/strategy_marketing"))

    response = supervisor.rag_agent.search(
        "Quelle strategie marketing ciblee pour un client insatisfait du service ?"
    )

    assert not response.data.empty
    assert "strategie" in response.answer.lower()
