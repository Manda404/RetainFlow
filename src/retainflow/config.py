"""Configuration loading utilities for RetainFlow."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class ChurnModelConfig:
    feature_table: str
    label_table: str
    prediction_table: str
    retention_queue_table: str
    retention_recommendation_table: str
    experiment_name: str
    registered_model_name: str
    register_model: bool
    prediction_threshold: float
    iterations: int
    learning_rate: float
    depth: int
    l2_leaf_reg: float
    random_strength: float
    bagging_temperature: float
    rsm: float
    min_data_in_leaf: int
    early_stopping_rounds: int
    postgres_dsn: str
    schema_name: str
    random_seed: int
    mlflow_enabled: bool
    mlflow_tracking_uri: str
    mlflow_artifact_uri: str
    mlflow_log_system_metrics: bool
    mlflow_ui_host: str
    mlflow_ui_port: int
    mlflow_ui_workers: int
    mlflow_ui_startup_timeout_seconds: int
    class_distribution_plot_path: Path
    training_curve_path: Path
    confusion_matrix_table_path: Path
    confusion_matrix_plot_path: Path
    threshold_grid_table_path: Path
    threshold_grid_plot_path: Path
    retention_queue_path: Path
    retention_recommendation_path: Path
    drift_report_path: Path
    drift_summary_path: Path
    drift_dashboard_path: Path
    drift_feature_exclusion_path: Path
    leakage_report_path: Path
    shap_summary_path: Path
    shap_agent_report_path: Path
    shap_feature_importance_plot_path: Path

    @property
    def feature_fqn(self) -> str:
        return f"{self.schema_name}.{self.feature_table}"

    @property
    def label_fqn(self) -> str:
        return f"{self.schema_name}.{self.label_table}"

    @property
    def prediction_fqn(self) -> str:
        return f"{self.schema_name}.{self.prediction_table}"

    @property
    def retention_queue_fqn(self) -> str:
        return f"{self.schema_name}.{self.retention_queue_table}"

    @property
    def retention_recommendation_fqn(self) -> str:
        return f"{self.schema_name}.{self.retention_recommendation_table}"

    @property
    def catalog(self) -> str:
        return self.schema_name


def load_yaml(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.exists() and not config_path.is_absolute():
        config_path = PROJECT_ROOT / config_path
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with config_path.open(encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def resolve_project_path(path: str | Path) -> Path:
    configured_path = Path(path)
    if configured_path.is_absolute():
        return configured_path
    return PROJECT_ROOT / configured_path


def load_churn_model_config(path: str | Path) -> ChurnModelConfig:
    raw = load_yaml(path)
    postgres = raw.get("postgres", {})
    mlflow = raw.get("mlflow", {})
    mlflow_ui = mlflow.get("ui", {})
    artifacts = raw.get("artifacts", {})
    schema_name = str(postgres.get("schema", raw.get("schema_name", "retainflow")))
    dsn_env = str(postgres.get("dsn_env", "RETAINFLOW_POSTGRES_DSN"))
    default_dsn = str(
        postgres.get("default_dsn", "postgresql://retainflow:retainflow@localhost:55432/retainflow")
    )
    configured_tracking_uri = str(
        mlflow.get("tracking_uri", "sqlite:////Users/surelmanda/.mlflow/mlflow.db")
    ).strip()

    return ChurnModelConfig(
        feature_table=str(raw.get("feature_table", "customer_360_snapshot")),
        label_table=str(raw.get("label_table", "churn_label")),
        prediction_table=str(raw.get("prediction_table", "churn_prediction")),
        retention_queue_table=str(raw.get("retention_queue_table", "retention_priority_queue")),
        retention_recommendation_table=str(
            raw.get("retention_recommendation_table", "retention_recommendation")
        ),
        experiment_name=str(raw.get("experiment_name", "RetainFlow/churn_model")),
        registered_model_name=str(raw.get("registered_model_name", "retainflow_churn_catboost")),
        register_model=bool(raw.get("register_model", False)),
        prediction_threshold=float(raw.get("prediction_threshold", 0.5)),
        iterations=int(raw.get("iterations", 300)),
        learning_rate=float(raw.get("learning_rate", 0.05)),
        depth=int(raw.get("depth", 6)),
        l2_leaf_reg=float(raw.get("l2_leaf_reg", 3.0)),
        random_strength=float(raw.get("random_strength", 1.0)),
        bagging_temperature=float(raw.get("bagging_temperature", 1.0)),
        rsm=float(raw.get("rsm", 1.0)),
        min_data_in_leaf=int(raw.get("min_data_in_leaf", 1)),
        early_stopping_rounds=int(raw.get("early_stopping_rounds", 50)),
        postgres_dsn=os.getenv(dsn_env, default_dsn),
        schema_name=schema_name,
        random_seed=int(raw.get("random_seed", 42)),
        mlflow_enabled=bool(mlflow.get("enabled", True)),
        mlflow_tracking_uri=configured_tracking_uri,
        mlflow_artifact_uri=str(
            mlflow.get("artifact_uri", "file:///Users/surelmanda/.mlflow/artifacts")
        ),
        mlflow_log_system_metrics=bool(mlflow.get("log_system_metrics", True)),
        mlflow_ui_host=str(mlflow_ui.get("host", "127.0.0.1")),
        mlflow_ui_port=int(mlflow_ui.get("port", 5050)),
        mlflow_ui_workers=int(mlflow_ui.get("workers", 1)),
        mlflow_ui_startup_timeout_seconds=int(mlflow_ui.get("startup_timeout_seconds", 15)),
        class_distribution_plot_path=resolve_project_path(
            artifacts.get(
                "class_distribution_plot_path",
                "reports/figures/class_distribution_by_split.png",
            )
        ),
        training_curve_path=resolve_project_path(
            artifacts.get("training_curve_path", "reports/tables/catboost_training_curve.csv")
        ),
        confusion_matrix_table_path=resolve_project_path(
            artifacts.get(
                "confusion_matrix_table_path",
                "reports/tables/confusion_matrix_by_split.csv",
            )
        ),
        confusion_matrix_plot_path=resolve_project_path(
            artifacts.get(
                "confusion_matrix_plot_path",
                "reports/figures/confusion_matrix_by_split.png",
            )
        ),
        threshold_grid_table_path=resolve_project_path(
            artifacts.get("threshold_grid_table_path", "reports/tables/threshold_tradeoff_grid.csv")
        ),
        threshold_grid_plot_path=resolve_project_path(
            artifacts.get("threshold_grid_plot_path", "reports/figures/threshold_tradeoff.png")
        ),
        retention_queue_path=resolve_project_path(
            artifacts.get("retention_queue_path", "reports/tables/retention_priority_queue.csv")
        ),
        retention_recommendation_path=resolve_project_path(
            artifacts.get(
                "retention_recommendation_path",
                "reports/tables/retention_recommendation.csv",
            )
        ),
        drift_report_path=resolve_project_path(
            artifacts.get("drift_report_path", "reports/tables/churn_drift_report.csv")
        ),
        drift_summary_path=resolve_project_path(
            artifacts.get("drift_summary_path", "reports/tables/churn_drift_summary.json")
        ),
        drift_dashboard_path=resolve_project_path(
            artifacts.get("drift_dashboard_path", "reports/drift/churn_drift_dashboard.html")
        ),
        drift_feature_exclusion_path=resolve_project_path(
            artifacts.get(
                "drift_feature_exclusion_path",
                "reports/tables/drift_feature_exclusions.json",
            )
        ),
        leakage_report_path=resolve_project_path(
            artifacts.get("leakage_report_path", "reports/tables/data_leakage_report.csv")
        ),
        shap_summary_path=resolve_project_path(
            artifacts.get("shap_summary_path", "reports/tables/shap_summary.csv")
        ),
        shap_agent_report_path=resolve_project_path(
            artifacts.get("shap_agent_report_path", "reports/tables/shap_agent_report.json")
        ),
        shap_feature_importance_plot_path=resolve_project_path(
            artifacts.get(
                "shap_feature_importance_plot_path",
                "reports/figures/shap_feature_importance.png",
            )
        ),
    )
