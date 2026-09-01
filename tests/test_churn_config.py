from retainflow.config import ChurnModelConfig, load_churn_model_config
from retainflow.logging import PROJECT_ROOT


def test_load_churn_model_config() -> None:
    config = load_churn_model_config("config/churn_model.yml")

    assert isinstance(config, ChurnModelConfig)
    assert config.catalog == "retainflow"
    assert config.feature_fqn == "retainflow.customer_360_snapshot"
    assert config.label_fqn == "retainflow.churn_label"
    assert config.prediction_fqn == "retainflow.churn_prediction"
    assert config.retention_queue_fqn == "retainflow.retention_priority_queue"
    assert config.retention_recommendation_fqn == "retainflow.retention_recommendation"
    assert config.registered_model_name == "retainflow_churn_catboost"
    assert config.iterations > 0
    assert 0 < config.learning_rate <= 1
    assert config.depth == 4
    assert config.l2_leaf_reg == 10.0
    assert config.random_strength == 2.0
    assert config.bagging_temperature == 1.0
    assert config.rsm == 0.8
    assert config.min_data_in_leaf == 50
    assert config.early_stopping_rounds == 50
    assert 0 < config.prediction_threshold < 1
    assert config.postgres_dsn.endswith(":55432/retainflow")
    assert config.mlflow_enabled is True
    assert config.mlflow_tracking_uri == "sqlite:////Users/surelmanda/.mlflow/mlflow.db"
    assert config.mlflow_artifact_uri == "file:///Users/surelmanda/.mlflow/artifacts"
    assert config.mlflow_log_system_metrics is True
    assert config.mlflow_ui_host == "127.0.0.1"
    assert config.mlflow_ui_port == 5050
    assert config.mlflow_ui_workers == 1
    assert config.mlflow_ui_startup_timeout_seconds == 45
    assert config.training_curve_path == PROJECT_ROOT / "reports/tables/catboost_training_curve.csv"
    assert config.confusion_matrix_table_path == (
        PROJECT_ROOT / "reports/tables/confusion_matrix_by_split.csv"
    )
    assert config.confusion_matrix_plot_path == (
        PROJECT_ROOT / "reports/figures/confusion_matrix_by_split.png"
    )
    assert config.threshold_grid_table_path == (
        PROJECT_ROOT / "reports/tables/threshold_tradeoff_grid.csv"
    )
    assert config.threshold_grid_plot_path == PROJECT_ROOT / "reports/figures/threshold_tradeoff.png"
    assert config.retention_queue_path == PROJECT_ROOT / "reports/tables/retention_priority_queue.csv"
    assert config.retention_recommendation_path == (
        PROJECT_ROOT / "reports/tables/retention_recommendation.csv"
    )
    assert config.drift_report_path == PROJECT_ROOT / "reports/tables/churn_drift_report.csv"
    assert config.drift_summary_path == PROJECT_ROOT / "reports/tables/churn_drift_summary.json"
    assert config.drift_dashboard_path == PROJECT_ROOT / "reports/drift/churn_drift_dashboard.html"
    assert config.drift_feature_exclusion_path == (
        PROJECT_ROOT / "reports/tables/drift_feature_exclusions.json"
    )
    assert config.leakage_report_path == PROJECT_ROOT / "reports/tables/data_leakage_report.csv"
    assert config.class_distribution_plot_path == (
        PROJECT_ROOT / "reports/figures/class_distribution_by_split.png"
    )
    assert config.shap_summary_path == PROJECT_ROOT / "reports/tables/shap_summary.csv"
    assert config.shap_agent_report_path == PROJECT_ROOT / "reports/tables/shap_agent_report.json"
    assert config.shap_feature_importance_plot_path == (
        PROJECT_ROOT / "reports/figures/shap_feature_importance.png"
    )


def test_load_churn_model_config_uses_yaml_mlflow_backend(monkeypatch) -> None:
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "file:///tmp/wrong-mlflow")
    config = load_churn_model_config("config/churn_model.yml")

    assert config.mlflow_tracking_uri == "sqlite:////Users/surelmanda/.mlflow/mlflow.db"
    assert config.mlflow_artifact_uri == "file:///Users/surelmanda/.mlflow/artifacts"


def test_load_churn_model_config_from_notebooks_cwd(monkeypatch) -> None:
    monkeypatch.chdir("notebooks")
    config = load_churn_model_config("config/churn_model.yml")

    assert config.feature_fqn == "retainflow.customer_360_snapshot"
