import pandas as pd

from retainflow.retention.priority import RetentionPriorityScorer


def _candidate(
    customer_id: str,
    churn_probability: float,
    total_annual_premium: float,
    customer_value_score: float,
    premium_increase: float,
    complaints: int,
) -> dict[str, object]:
    return {
        "observation_date": "2026-06-30",
        "customer_id": customer_id,
        "split_name": "backtest",
        "first_name": "Jean",
        "last_name": customer_id,
        "customer_segment": "HIGH_VALUE" if total_annual_premium > 1000 else "PRICE_SENSITIVE",
        "region": "Ile-de-France",
        "agency_name": "Agence Paris",
        "main_product_family": "AUTO",
        "churn_probability": churn_probability,
        "predicted_churn_label": int(churn_probability >= 0.2),
        "churn_risk_band": "HIGH",
        "model_name": "retainflow_churn_catboost",
        "model_version": None,
        "mlflow_run_id": "run-1",
        "scored_at": "2026-08-31T07:00:00",
        "estimated_income_band": "HIGH",
        "digital_profile": "MEDIUM",
        "price_sensitivity_score": 0.7,
        "service_sensitivity_score": 0.7,
        "digital_engagement_score": 0.4,
        "loyalty_score": 0.6,
        "claim_propensity_score": 0.5,
        "consent_email": True,
        "consent_sms": False,
        "consent_phone": True,
        "preferred_channel_code": "CH_PHONE",
        "preferred_channel_name": "Telephone",
        "agency_type": "BRANCH",
        "urbanicity": "URBAN",
        "tenure_months": 24,
        "active_policy_count": 2,
        "number_of_products": 2,
        "total_annual_premium": total_annual_premium,
        "total_claims_12m": 1,
        "total_claim_amount_12m": 500,
        "payment_incidents_6m": 0,
        "complaints_6m": complaints,
        "interactions_3m": 2,
        "days_since_last_contact": 45,
        "digital_sessions_30d": 1,
        "email_open_rate_6m": 0.3,
        "premium_increase_pct_max_12m": premium_increase,
        "avg_satisfaction_score_12m": 3.5,
        "renewal_days_min": 20,
        "customer_value_score": customer_value_score,
        "late_payment_count_12m": 0,
        "rejected_payment_count_12m": 0,
        "service_case_count_12m": complaints,
        "unresolved_case_count_12m": 0,
        "retention_offer_count_12m": 1,
        "retention_acceptance_rate_12m": 0.5,
        "quote_count_6m": 1,
        "competitor_price_index_avg_6m": 0.92,
        "campaign_response_rate_6m": 0.4,
        "highest_coverage_tier": "PREMIUM",
    }


def test_retention_priority_scorer_orders_business_priority() -> None:
    candidates = pd.DataFrame(
        [
            _candidate("CUST-LOW", 0.25, 300, 0.3, 0.02, 0),
            _candidate("CUST-HIGH", 0.55, 2400, 0.9, 0.15, 2),
        ]
    )

    queue = RetentionPriorityScorer().score(candidates)

    assert queue.iloc[0]["customer_id"] == "CUST-HIGH"
    assert queue.iloc[0]["priority_tier"] in {"HIGH", "CRITICAL"}
    assert queue.iloc[0]["recommended_action_type"] == "LOYALTY_DISCOUNT_REVIEW"
    assert queue.iloc[0]["recommended_channel"] == "PHONE"
    assert "recent premium increase" in queue.iloc[0]["action_reason"]


def test_retention_priority_scorer_handles_empty_candidates() -> None:
    queue = RetentionPriorityScorer().score(pd.DataFrame())

    assert queue.empty
    assert "priority_score" in queue.columns
