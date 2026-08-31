import json

import pandas as pd

from retainflow.explainability.shap import ShapExplainer


def test_shap_agent_report_contract(tmp_path) -> None:
    explainer = ShapExplainer(model=object(), feature_names=["tenure_months", "region"])
    summary = pd.DataFrame(
        [
            {
                "rank": 1,
                "feature": "tenure_months",
                "feature_type": "numeric",
                "mean_abs_shap": 0.42,
                "mean_shap": -0.12,
                "positive_impact_share": 0.25,
                "normalized_importance_pct": 70.0,
                "impact_direction": "decreases_churn_risk",
            },
            {
                "rank": 2,
                "feature": "region",
                "feature_type": "categorical",
                "mean_abs_shap": 0.18,
                "mean_shap": 0.04,
                "positive_impact_share": 0.58,
                "normalized_importance_pct": 30.0,
                "impact_direction": "increases_churn_risk",
            },
        ]
    )

    report = explainer.build_agent_report(
        summary=summary,
        metrics_by_split={"test": {"auc": 0.81}},
        model_name="retainflow_churn_catboost",
        run_id="run-123",
        sample_size=500,
    )
    report_path = explainer.save_agent_report(report, tmp_path / "shap_agent_report.json")

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "1.0"
    assert payload["mlflow_run_id"] == "run-123"
    assert payload["metrics_by_split"]["test"]["auc"] == 0.81
    assert payload["top_features"][0]["feature"] == "tenure_months"
    assert "interpretation_contract" in payload
