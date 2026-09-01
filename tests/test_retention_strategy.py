import pandas as pd

from retainflow.retention.strategy import RetentionStrategyEngine


def _priority_row(action_type: str = "LOYALTY_DISCOUNT_REVIEW") -> dict[str, object]:
    return {
        "observation_date": "2026-06-30",
        "customer_id": "CUST-1",
        "split_name": "backtest",
        "first_name": "Nadia",
        "last_name": "Martin",
        "priority_tier": "HIGH",
        "priority_score": 58.2,
        "churn_probability": 0.42,
        "expected_saved_value": 280.0,
        "recommended_action_type": action_type,
        "recommended_channel": "PHONE",
        "estimated_offer_value": 120.0,
        "action_reason": "hausse de prime recente; renouvellement proche",
        "mlflow_run_id": "run-1",
    }


def test_retention_strategy_engine_builds_human_review_recommendation() -> None:
    recommendations = RetentionStrategyEngine().recommend(pd.DataFrame([_priority_row()]))
    row = recommendations.iloc[0]

    assert row["recommendation_id"].startswith("REC_")
    assert row["recommended_offer"] == "Remise fidelite controlee - budget max 120.00 EUR"
    assert row["human_review_status"] == "PENDING_REVIEW"
    assert row["approval_decision"] is None
    assert "Nadia Martin" in row["advisor_message"]
    assert "hausse de prime recente" in row["decision_rationale"]


def test_retention_strategy_engine_falls_back_to_proactive_check() -> None:
    recommendations = RetentionStrategyEngine().recommend(
        pd.DataFrame([_priority_row("UNKNOWN_ACTION")])
    )

    assert "Controle retention proactif" in recommendations.iloc[0]["recommended_offer"]


def test_retention_strategy_engine_handles_empty_queue() -> None:
    recommendations = RetentionStrategyEngine().recommend(pd.DataFrame())

    assert recommendations.empty
    assert "recommendation_id" in recommendations.columns
