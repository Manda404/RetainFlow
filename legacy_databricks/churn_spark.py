"""CatBoost churn training and scoring pipeline."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

import mlflow
import mlflow.catboost
import pandas as pd
from catboost import CatBoostClassifier, Pool
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from retainflow.config import ChurnModelConfig


NUMERIC_FEATURES = [
    "tenure_months",
    "active_policy_count",
    "number_of_products",
    "total_annual_premium",
    "total_claims_12m",
    "total_claim_amount_12m",
    "payment_incidents_6m",
    "complaints_6m",
    "interactions_3m",
    "days_since_last_contact",
    "digital_sessions_30d",
    "email_open_rate_6m",
    "premium_increase_pct_max_12m",
    "avg_satisfaction_score_12m",
    "renewal_days_min",
    "customer_value_score",
    "price_sensitivity_score",
    "digital_engagement_score",
    "loyalty_score",
]

CATEGORICAL_FEATURES = [
    "customer_segment",
    "estimated_income_band",
    "digital_profile",
]

FEATURE_COLUMNS = NUMERIC_FEATURES + CATEGORICAL_FEATURES


def build_training_dataset(spark: SparkSession, config: ChurnModelConfig) -> DataFrame:
    features = spark.table(config.feature_fqn)
    labels = spark.table(config.label_fqn)

    return (
        features.alias("f")
        .join(
            labels.select(
                "observation_date",
                "customer_id",
                F.col("churn_label").cast("int").alias("label"),
                F.col("churn_probability").alias("synthetic_churn_probability"),
                F.col("churn_risk_band").alias("synthetic_churn_risk_band"),
                "label_reason",
            ).alias("l"),
            on=["observation_date", "customer_id"],
            how="inner",
        )
        .withColumn("split_bucket", F.pmod(F.xxhash64("customer_id"), F.lit(100)))
    )


def to_modeling_pandas(dataset: DataFrame) -> pd.DataFrame:
    id_columns = ["observation_date", "customer_id", "split_bucket"]
    label_columns = [
        "label",
        "synthetic_churn_probability",
        "synthetic_churn_risk_band",
        "label_reason",
    ]
    selected_columns = id_columns + FEATURE_COLUMNS + label_columns

    dataset_pd = dataset.select(*selected_columns).toPandas()

    for column in CATEGORICAL_FEATURES:
        dataset_pd[column] = dataset_pd[column].fillna("UNKNOWN").astype(str)

    for column in NUMERIC_FEATURES:
        dataset_pd[column] = pd.to_numeric(dataset_pd[column], errors="coerce").fillna(0.0)

    dataset_pd["observation_date"] = pd.to_datetime(dataset_pd["observation_date"]).dt.date
    return dataset_pd


def split_dataset(dataset: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train = dataset[dataset["split_bucket"] < 70].copy()
    valid = dataset[(dataset["split_bucket"] >= 70) & (dataset["split_bucket"] < 85)].copy()
    test = dataset[dataset["split_bucket"] >= 85].copy()
    return train, valid, test


def make_pool(frame: pd.DataFrame) -> Pool:
    cat_feature_indices = [FEATURE_COLUMNS.index(column) for column in CATEGORICAL_FEATURES]
    return Pool(
        frame[FEATURE_COLUMNS],
        label=frame["label"],
        cat_features=cat_feature_indices,
    )


def evaluate_classifier(
    model: CatBoostClassifier,
    pool: Pool,
    frame: pd.DataFrame,
    prediction_threshold: float,
) -> dict[str, float]:
    probabilities = model.predict_proba(pool)[:, 1]
    predictions = (probabilities >= prediction_threshold).astype(int)
    labels = frame["label"].to_numpy()

    return {
        "auc": roc_auc_score(labels, probabilities),
        "average_precision": average_precision_score(labels, probabilities),
        "accuracy": accuracy_score(labels, predictions),
        "f1": f1_score(labels, predictions),
        "precision": precision_score(labels, predictions, zero_division=0),
        "recall": recall_score(labels, predictions, zero_division=0),
    }


def build_split_summary(
    train: pd.DataFrame,
    valid: pd.DataFrame,
    test: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    for split_name, frame in (("train", train), ("validation", valid), ("test", test)):
        rows.append(
            {
                "split": split_name,
                "rows": len(frame),
                "customers": frame["customer_id"].nunique(),
                "churn_rate": frame["label"].mean(),
                "positive_labels": int(frame["label"].sum()),
                "negative_labels": int((frame["label"] == 0).sum()),
            }
        )
    return pd.DataFrame(rows)


def build_label_distribution(dataset: pd.DataFrame) -> pd.DataFrame:
    return (
        dataset.groupby(["synthetic_churn_risk_band", "label"], dropna=False)
        .agg(
            rows=("customer_id", "count"),
            avg_synthetic_churn_probability=("synthetic_churn_probability", "mean"),
        )
        .reset_index()
        .sort_values(["synthetic_churn_risk_band", "label"])
    )


def build_feature_profile(dataset: pd.DataFrame) -> pd.DataFrame:
    numeric_profile = dataset[NUMERIC_FEATURES].describe().transpose().reset_index()
    numeric_profile = numeric_profile.rename(columns={"index": "feature"})
    numeric_profile["feature_type"] = "numeric"

    categorical_rows = []
    for column in CATEGORICAL_FEATURES:
        categorical_rows.append(
            {
                "feature": column,
                "feature_type": "categorical",
                "count": dataset[column].count(),
                "unique": dataset[column].nunique(),
                "top": dataset[column].mode(dropna=False).iloc[0],
                "freq": dataset[column].value_counts(dropna=False).iloc[0],
            }
        )

    categorical_profile = pd.DataFrame(categorical_rows)
    return pd.concat([numeric_profile, categorical_profile], ignore_index=True, sort=False)


def build_feature_importance(
    model: CatBoostClassifier,
    train_pool: Pool,
) -> pd.DataFrame:
    return (
        pd.DataFrame(
            {
                "feature": FEATURE_COLUMNS,
                "importance": model.get_feature_importance(train_pool),
            }
        )
        .sort_values("importance", ascending=False)
        .reset_index(drop=True)
    )


def build_confusion_matrix(
    model: CatBoostClassifier,
    pool: Pool,
    frame: pd.DataFrame,
    prediction_threshold: float,
) -> pd.DataFrame:
    probabilities = model.predict_proba(pool)[:, 1]
    predictions = (probabilities >= prediction_threshold).astype(int)
    matrix = confusion_matrix(frame["label"].to_numpy(), predictions, labels=[0, 1])
    return pd.DataFrame(
        [
            {"actual": 0, "predicted": 0, "rows": int(matrix[0, 0])},
            {"actual": 0, "predicted": 1, "rows": int(matrix[0, 1])},
            {"actual": 1, "predicted": 0, "rows": int(matrix[1, 0])},
            {"actual": 1, "predicted": 1, "rows": int(matrix[1, 1])},
        ]
    )


def log_dataframe_artifact(frame: pd.DataFrame, artifact_path: str) -> None:
    mlflow.log_text(frame.to_csv(index=False), artifact_path)


def log_churn_artifacts(
    config: ChurnModelConfig,
    dataset: pd.DataFrame,
    split_summary: pd.DataFrame,
    label_distribution: pd.DataFrame,
    feature_profile: pd.DataFrame,
    feature_importance: pd.DataFrame,
    valid_confusion_matrix: pd.DataFrame,
    test_confusion_matrix: pd.DataFrame,
    scores: pd.DataFrame,
) -> None:
    mlflow.log_dict(asdict(config), "config/churn_model_config.json")
    mlflow.log_dict(
        {
            "numeric_features": NUMERIC_FEATURES,
            "categorical_features": CATEGORICAL_FEATURES,
            "feature_columns": FEATURE_COLUMNS,
        },
        "features/feature_contract.json",
    )
    log_dataframe_artifact(split_summary, "data/split_summary.csv")
    log_dataframe_artifact(label_distribution, "data/label_distribution.csv")
    log_dataframe_artifact(feature_profile, "data/feature_profile.csv")
    log_dataframe_artifact(feature_importance, "model/feature_importance.csv")
    log_dataframe_artifact(valid_confusion_matrix, "metrics/valid_confusion_matrix.csv")
    log_dataframe_artifact(test_confusion_matrix, "metrics/test_confusion_matrix.csv")
    log_dataframe_artifact(dataset.head(200), "samples/training_dataset_sample.csv")
    log_dataframe_artifact(scores.head(200), "samples/churn_prediction_sample.csv")


def make_scores(
    model: CatBoostClassifier,
    dataset: pd.DataFrame,
    config: ChurnModelConfig,
    scoring_run_id: str,
) -> pd.DataFrame:
    cat_feature_indices = [FEATURE_COLUMNS.index(column) for column in CATEGORICAL_FEATURES]
    all_pool = Pool(dataset[FEATURE_COLUMNS], cat_features=cat_feature_indices)

    scores = dataset[["observation_date", "customer_id"]].copy()
    scores["churn_probability"] = model.predict_proba(all_pool)[:, 1]
    scores["predicted_churn_label"] = (
        scores["churn_probability"] >= config.prediction_threshold
    ).astype(int)
    scores["churn_risk_band"] = pd.cut(
        scores["churn_probability"],
        bins=[-0.001, 0.18, 0.35, 0.55, 1.0],
        labels=["LOW", "MEDIUM", "HIGH", "VERY_HIGH"],
    ).astype(str)
    scores["model_name"] = config.registered_model_name
    scores["model_version"] = None
    scores["scoring_run_id"] = scoring_run_id
    scores["scored_at"] = pd.Timestamp.utcnow().to_pydatetime()
    return scores


def train_and_score_churn_model(spark: SparkSession, config: ChurnModelConfig) -> dict[str, Any]:
    dataset_spark = build_training_dataset(spark, config)
    dataset_pd = to_modeling_pandas(dataset_spark)
    train_pd, valid_pd, test_pd = split_dataset(dataset_pd)
    split_summary = build_split_summary(train_pd, valid_pd, test_pd)
    label_distribution = build_label_distribution(dataset_pd)
    feature_profile = build_feature_profile(dataset_pd)

    train_pool = make_pool(train_pd)
    valid_pool = make_pool(valid_pd)
    test_pool = make_pool(test_pd)

    model = CatBoostClassifier(
        iterations=config.iterations,
        learning_rate=config.learning_rate,
        depth=config.depth,
        loss_function="Logloss",
        eval_metric="AUC",
        random_seed=42,
        auto_class_weights="Balanced",
        verbose=50,
    )

    mlflow.set_experiment(config.experiment_name)

    with mlflow.start_run(run_name="retainflow_churn_catboost") as run:
        mlflow.log_params(
            {
                **asdict(config),
                "feature_table_fqn": config.feature_fqn,
                "label_table_fqn": config.label_fqn,
                "prediction_table_fqn": config.prediction_fqn,
                "numeric_feature_count": len(NUMERIC_FEATURES),
                "categorical_feature_count": len(CATEGORICAL_FEATURES),
                "categorical_features": json.dumps(CATEGORICAL_FEATURES),
            }
        )

        model.fit(train_pool, eval_set=valid_pool, use_best_model=True)

        valid_metrics = evaluate_classifier(
            model, valid_pool, valid_pd, config.prediction_threshold
        )
        test_metrics = evaluate_classifier(model, test_pool, test_pd, config.prediction_threshold)
        valid_confusion_matrix = build_confusion_matrix(
            model, valid_pool, valid_pd, config.prediction_threshold
        )
        test_confusion_matrix = build_confusion_matrix(
            model, test_pool, test_pd, config.prediction_threshold
        )
        feature_importance = build_feature_importance(model, train_pool)
        scoring_run_id = run.info.run_id
        scores_pd = make_scores(model, dataset_pd, config, scoring_run_id)

        mlflow.set_tags(
            {
                "project": "RetainFlow",
                "pipeline_stage": "churn_model_training",
                "model_family": "gradient_boosting",
                "model_library": "catboost",
                "data_source": "databricks_delta",
                "dataset_engine": "spark_to_pandas",
            }
        )

        for metric_name, metric_value in valid_metrics.items():
            mlflow.log_metric(f"valid_{metric_name}", metric_value)
        for metric_name, metric_value in test_metrics.items():
            mlflow.log_metric(f"test_{metric_name}", metric_value)

        mlflow.log_metric("dataset_rows", len(dataset_pd))
        mlflow.log_metric("train_rows", len(train_pd))
        mlflow.log_metric("valid_rows", len(valid_pd))
        mlflow.log_metric("test_rows", len(test_pd))
        mlflow.log_metric("scored_rows", len(scores_pd))
        mlflow.log_metric("positive_labels", int(dataset_pd["label"].sum()))
        mlflow.log_metric("negative_labels", int((dataset_pd["label"] == 0).sum()))
        mlflow.log_metric("global_churn_rate", float(dataset_pd["label"].mean()))
        mlflow.log_metric(
            "avg_predicted_churn_probability",
            float(scores_pd["churn_probability"].mean()),
        )
        mlflow.log_metric(
            "max_predicted_churn_probability",
            float(scores_pd["churn_probability"].max()),
        )
        mlflow.log_metric(
            "min_predicted_churn_probability",
            float(scores_pd["churn_probability"].min()),
        )

        log_churn_artifacts(
            config=config,
            dataset=dataset_pd,
            split_summary=split_summary,
            label_distribution=label_distribution,
            feature_profile=feature_profile,
            feature_importance=feature_importance,
            valid_confusion_matrix=valid_confusion_matrix,
            test_confusion_matrix=test_confusion_matrix,
            scores=scores_pd,
        )

        log_model_kwargs = {
            "cb_model": model,
            "artifact_path": "model",
        }
        if config.register_model:
            log_model_kwargs["registered_model_name"] = config.registered_model_name

        mlflow.catboost.log_model(**log_model_kwargs)

    scores_spark = spark.createDataFrame(scores_pd)
    (
        scores_spark.write.format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .saveAsTable(config.prediction_fqn)
    )

    return {
        "config": asdict(config),
        "valid_metrics": valid_metrics,
        "test_metrics": test_metrics,
        "mlflow_run_id": scoring_run_id,
        "rows": {
            "dataset": len(dataset_pd),
            "train": len(train_pd),
            "valid": len(valid_pd),
            "test": len(test_pd),
            "scores": len(scores_pd),
        },
        "prediction_table": config.prediction_fqn,
    }
