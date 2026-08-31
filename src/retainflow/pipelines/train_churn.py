"""CatBoost training pipeline with configurable MLflow tracking."""

from __future__ import annotations

import argparse
import os
import subprocess
import warnings
from pathlib import Path
from typing import Any

import pandas as pd
from catboost import CatBoostClassifier, Pool

from retainflow.config import PROJECT_ROOT, ChurnModelConfig, load_churn_model_config
from retainflow.data.dataset import ChurnDatasetLoader
from retainflow.data.splitting import TemporalDatasetSplitter
from retainflow.evaluation.metrics import BinaryClassifierEvaluator, ConfusionMatrixReporter
from retainflow.evaluation.visualization import ClassDistributionPlotter
from retainflow.features.engineering import ChurnFeatureEngineer
from retainflow.features.preprocessing import FEATURE_COLUMNS, ChurnPreprocessor
from retainflow.logging import get_logger
from retainflow.models.catboost_churn import (
    ChurnModelTrainer,
    build_shap_summary,
    predict_positive_class_probability,
    shap_version,
)
from retainflow.tracking.runtime import configure_local_mlflow_runtime

logger = get_logger(__name__)

__all__ = [
    "ChurnModelTrainer",
    "build_shap_summary",
    "configure_mlflow",
    "log_mlflow_dataset",
    "log_mlflow_provenance",
    "main",
    "predict_positive_class_probability",
    "save_predictions",
    "shap_version",
    "train_churn_model",
]


def configure_mlflow(config: ChurnModelConfig) -> str:
    """Configure MLflow from project config and return the active tracking URI."""
    configure_local_mlflow_runtime()
    import mlflow

    if not config.mlflow_enabled:
        logger.info("MLflow tracking is disabled in config")
        return ""

    os.environ["MLFLOW_TRACKING_URI"] = config.mlflow_tracking_uri
    os.environ["MLFLOW_REGISTRY_URI"] = config.mlflow_tracking_uri
    mlflow.set_tracking_uri(config.mlflow_tracking_uri)
    mlflow.set_registry_uri(config.mlflow_tracking_uri)
    logger.info("Using configured MLflow tracking URI: %s", config.mlflow_tracking_uri)

    experiment = mlflow.get_experiment_by_name(config.experiment_name)
    if experiment is None:
        experiment_id = mlflow.create_experiment(
            config.experiment_name,
            artifact_location=config.mlflow_artifact_uri,
            tags={"project": "retainflow", "environment": "development"},
        )
        mlflow.set_experiment(experiment_id=experiment_id)
    else:
        mlflow.set_experiment(experiment_id=experiment.experiment_id)

    return mlflow.get_tracking_uri()


def current_git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


def log_mlflow_provenance() -> None:
    import mlflow

    mlflow.set_tags(
        {
            "project": "retainflow",
            "environment": "development",
            "git_commit": current_git_commit() or "unknown",
            "mlflow_version": mlflow.__version__,
        }
    )
    mlflow.log_artifact(
        str(PROJECT_ROOT / "config" / "churn_model.yml"), artifact_path="configuration/yaml"
    )
    for filename in ("pyproject.toml", "poetry.lock"):
        path = PROJECT_ROOT / filename
        if path.exists():
            mlflow.log_artifact(str(path), artifact_path="environment")


def log_mlflow_dataset(dataset: pd.DataFrame, config: ChurnModelConfig) -> Any:
    import mlflow

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="The specified dataset source can be interpreted")
        warnings.filterwarnings("ignore", message="Hint: Inferred schema contains integer column.*")
        mlflow_dataset = mlflow.data.from_pandas(
            dataset,
            targets="churn_label",
            name="retainflow_churn_modeling_dataset",
        )
        mlflow.log_input(mlflow_dataset, context="training")
    mlflow.log_params(
        {
            "feature_table": config.feature_fqn,
            "label_table": config.label_fqn,
            "prediction_table": config.prediction_fqn,
            "dataset_rows": len(dataset),
            "dataset_features": len(FEATURE_COLUMNS),
            "global_churn_rate": float(dataset["churn_label"].mean()),
        }
    )
    return mlflow_dataset


def _risk_band(probability: float) -> str:
    if probability >= 0.08:
        return "VERY_HIGH"
    if probability >= 0.05:
        return "HIGH"
    if probability >= 0.035:
        return "MEDIUM"
    return "LOW"


def save_predictions(
    config: ChurnModelConfig,
    dataset: pd.DataFrame,
    probabilities_by_split: dict[str, list[float]],
    run_id: str,
) -> None:
    from retainflow.db import postgres_connection

    rows = []
    for split_name, probabilities in probabilities_by_split.items():
        subset = dataset.loc[
            dataset["split_name"] == split_name, ["observation_date", "customer_id"]
        ]
        for (_, row), probability in zip(subset.iterrows(), probabilities, strict=True):
            rows.append(
                (
                    row["observation_date"],
                    row["customer_id"],
                    split_name,
                    round(float(probability), 6),
                    1 if probability >= config.prediction_threshold else 0,
                    _risk_band(float(probability)),
                    config.registered_model_name,
                    None,
                    run_id,
                )
            )

    logger.info("Saving %s predictions to %s", len(rows), config.prediction_fqn)
    with postgres_connection(config.postgres_dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {config.prediction_fqn} (
                  observation_date date NOT NULL,
                  customer_id text NOT NULL REFERENCES {config.schema_name}.dim_customer(customer_id),
                  split_name text NOT NULL CHECK (split_name IN ('validation', 'test', 'backtest', 'scoring')),
                  churn_probability numeric(8,6) NOT NULL,
                  predicted_churn_label integer NOT NULL CHECK (predicted_churn_label IN (0, 1)),
                  churn_risk_band text NOT NULL CHECK (churn_risk_band IN ('LOW', 'MEDIUM', 'HIGH', 'VERY_HIGH')),
                  model_name text NOT NULL,
                  model_version text,
                  mlflow_run_id text NOT NULL,
                  scored_at timestamptz NOT NULL DEFAULT now(),
                  PRIMARY KEY (observation_date, customer_id, model_name, mlflow_run_id)
                )
                """
            )
            cur.executemany(
                f"""
                INSERT INTO {config.prediction_fqn}
                (observation_date,customer_id,split_name,churn_probability,predicted_churn_label,churn_risk_band,model_name,model_version,mlflow_run_id)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (observation_date, customer_id, model_name, mlflow_run_id)
                DO UPDATE SET
                  churn_probability = EXCLUDED.churn_probability,
                  predicted_churn_label = EXCLUDED.predicted_churn_label,
                  churn_risk_band = EXCLUDED.churn_risk_band,
                  scored_at = now()
                """,
                rows,
            )
        conn.commit()


def train_churn_model(config: ChurnModelConfig) -> dict[str, Any]:
    logger.info("Starting churn training pipeline")
    configure_local_mlflow_runtime()
    import mlflow
    import mlflow.catboost

    loader = ChurnDatasetLoader(config)
    feature_engineer = ChurnFeatureEngineer()
    preprocessor = ChurnPreprocessor()
    splitter = TemporalDatasetSplitter()

    raw_dataset = loader.load()

    feature_dataset = feature_engineer.transform(raw_dataset)
    raw_splits = splitter.split(feature_dataset)
    preprocessor.fit(raw_splits["train"].data)
    dataset = pd.concat(
        [preprocessor.transform(split.data) for split in raw_splits.values()],
        ignore_index=True,
    )
    splits = splitter.split(dataset)
    class_distribution_plotter = ClassDistributionPlotter(size=(15, 6))

    train_x, train_y = splits["train"].features, splits["train"].target
    valid_x, valid_y = splits["validation"].features, splits["validation"].target
    test_x, test_y = splits["test"].features, splits["test"].target
    backtest_x, backtest_y = splits["backtest"].features, splits["backtest"].target

    cat_features = preprocessor.catboost_feature_indices()
    train_pool = Pool(train_x, label=train_y, cat_features=cat_features)
    valid_pool = Pool(valid_x, label=valid_y, cat_features=cat_features)
    test_pool = Pool(test_x, label=test_y, cat_features=cat_features)
    backtest_pool = Pool(backtest_x, label=backtest_y, cat_features=cat_features)

    model = CatBoostClassifier(
        iterations=config.iterations,
        learning_rate=config.learning_rate,
        depth=config.depth,
        loss_function="Logloss",
        eval_metric="AUC",
        random_seed=config.random_seed,
        verbose=False,
        allow_writing_files=False,
    )
    evaluator = BinaryClassifierEvaluator(threshold=config.prediction_threshold)
    trainer = ChurnModelTrainer(config=config, model=model, evaluator=evaluator)

    tracking_uri = configure_mlflow(config)

    with mlflow.start_run(
        run_name="retainflow_churn_catboost_postgres",
        tags={
            "project": "retainflow",
            "environment": "development",
            "stage": "model_training",
            "model_name": "CatBoostClassifier",
            "data_source": "postgresql",
        },
        description="CatBoost churn model trained from PostgreSQL customer 360 snapshots.",
        log_system_metrics=config.mlflow_log_system_metrics,
    ) as run:
        logger.info("MLflow run started: %s", run.info.run_id)
        log_mlflow_dataset(dataset, config)
        log_mlflow_provenance()
        mlflow.log_params(
            {
                "model_type": "CatBoostClassifier",
                "iterations": config.iterations,
                "learning_rate": config.learning_rate,
                "depth": config.depth,
                "prediction_threshold": config.prediction_threshold,
                "random_seed": config.random_seed,
                "shap_version": shap_version(),
            }
        )
        mlflow.log_table(
            pd.DataFrame(
                {
                    "feature": FEATURE_COLUMNS,
                    "is_categorical": [
                        index in cat_features for index in range(len(FEATURE_COLUMNS))
                    ],
                }
            ),
            "tables/feature_contract.json",
        )

        trainer.fit(train_pool, valid_pool)

        class_distribution_plot_path = config.class_distribution_plot_path
        class_distribution = class_distribution_plotter.distribution_frame(dataset)
        mlflow.log_table(class_distribution, "tables/class_distribution_by_split.json")
        class_distribution_ax = class_distribution_plotter.plot(
            dataset, path=class_distribution_plot_path
        )
        mlflow.log_figure(class_distribution_ax.figure, "figures/class_distribution_by_split.png")

        training_curve = trainer.training_curve()
        training_curve_path = config.training_curve_path
        training_curve_path.parent.mkdir(parents=True, exist_ok=True)
        training_curve.to_csv(training_curve_path, index=False)
        mlflow.log_table(training_curve, "tables/catboost_training_curve.json")

        metrics_by_split, probabilities_by_split = trainer.evaluate(
            pools_by_split={
                "validation": valid_pool,
                "test": test_pool,
                "backtest": backtest_pool,
            },
            targets_by_split={
                "validation": valid_y,
                "test": test_y,
                "backtest": backtest_y,
            },
        )
        for split_name, metrics in metrics_by_split.items():
            for metric_name, value in metrics.items():
                mlflow.log_metric(f"{split_name}_{metric_name}", value)
        mlflow.log_table(
            pd.DataFrame(metrics_by_split).T.reset_index(names="split_name"),
            "tables/metrics_by_split.json",
        )

        confusion_reporter = ConfusionMatrixReporter(
            threshold=config.prediction_threshold,
            size=(15, 6),
        )
        confusion_matrix_frame = confusion_reporter.matrix_frame(
            targets_by_split={
                "test": test_y,
                "backtest": backtest_y,
            },
            probabilities_by_split=probabilities_by_split,
        )
        confusion_matrix_table_path = config.confusion_matrix_table_path
        confusion_matrix_plot_path = config.confusion_matrix_plot_path
        confusion_matrix_table_path.parent.mkdir(parents=True, exist_ok=True)
        confusion_matrix_frame.to_csv(confusion_matrix_table_path, index=False)
        confusion_matrix_figure = confusion_reporter.plot(
            confusion_matrix_frame,
            path=confusion_matrix_plot_path,
        )
        mlflow.log_table(confusion_matrix_frame, "tables/confusion_matrix_by_split.json")
        mlflow.log_figure(confusion_matrix_figure, "figures/confusion_matrix_by_split.png")

        mlflow.log_metric("train_rows", len(train_x))
        mlflow.log_metric("validation_rows", len(valid_x))
        mlflow.log_metric("test_rows", len(test_x))
        mlflow.log_metric("backtest_rows", len(backtest_x))

        shap_sample_size = 1000
        shap_explainer = trainer.shap_explainer()
        shap_summary = shap_explainer.summary_frame(train_pool, sample_size=shap_sample_size)
        shap_path = config.shap_summary_path
        shap_report_path = config.shap_agent_report_path
        shap_plot_path = config.shap_feature_importance_plot_path
        shap_explainer.save_summary_csv(shap_summary, shap_path)
        mlflow.log_table(shap_summary, "tables/shap_summary.json")
        shap_report = shap_explainer.build_agent_report(
            summary=shap_summary,
            metrics_by_split=metrics_by_split,
            model_name=config.registered_model_name,
            run_id=run.info.run_id,
            sample_size=shap_sample_size,
        )
        shap_explainer.save_agent_report(shap_report, shap_report_path)
        shap_explainer.plot_feature_importance(shap_summary, shap_plot_path)
        mlflow.log_dict(shap_report, "explainability/shap_agent_report.json")
        mlflow.log_artifact(str(shap_plot_path), artifact_path="figures")

        mlflow.catboost.log_model(model, artifact_path="model")
        save_predictions(config, dataset, probabilities_by_split, run.info.run_id)

        logger.info("Logged model and SHAP summary to MLflow")
        return {
            "run_id": run.info.run_id,
            "metrics": metrics_by_split,
            "tracking_uri": tracking_uri,
            "training_curve_path": str(training_curve_path),
            "class_distribution_plot_path": str(class_distribution_plot_path),
            "confusion_matrix_table_path": str(confusion_matrix_table_path),
            "confusion_matrix_plot_path": str(confusion_matrix_plot_path),
            "shap_report_path": str(shap_report_path),
            "shap_plot_path": str(shap_plot_path),
            "shap_top_features": shap_summary.head(10).to_dict(orient="records"),
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the RetainFlow churn model.")
    parser.add_argument(
        "--config",
        default="config/churn_model.yml",
        help="Path to the churn model YAML configuration.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_churn_model_config(Path(args.config))
    result = train_churn_model(config)
    logger.info("Training complete: %s", result)
    print(result)


if __name__ == "__main__":
    main()
