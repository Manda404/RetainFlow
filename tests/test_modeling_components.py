import pandas as pd

from retainflow.data.splitting import TemporalDatasetSplitter
from retainflow.evaluation.metrics import BinaryClassifierEvaluator, ConfusionMatrixReporter
from retainflow.evaluation.visualization import ClassDistributionPlotter
from retainflow.features.engineering import LABEL_AUDIT_COLUMNS, ChurnFeatureEngineer
from retainflow.features.preprocessing import (
    CATEGORICAL_FEATURES,
    FEATURE_COLUMNS,
    NUMERIC_FEATURES,
    ChurnPreprocessor,
)


def _minimal_frame() -> pd.DataFrame:
    rows = []
    for split_name, observation_date, label in [
        ("train", "2023-12-31", 0),
        ("validation", "2024-12-31", 1),
        ("test", "2025-12-31", 0),
        ("backtest", "2026-06-30", 1),
    ]:
        row = {
            "observation_date": observation_date,
            "customer_id": f"CUST-{split_name}",
            "split_name": split_name,
            "churn_label": label,
            "birth_date": "1985-01-01",
            "acquisition_date": "2020-01-01",
            "churn_date": observation_date if label else None,
            "customer_lifecycle_status": "CHURNED_WITHIN_HORIZON"
            if label
            else "ACTIVE_OBSERVED",
        }
        row.update({column: 1.0 for column in NUMERIC_FEATURES})
        row.update({column: None for column in CATEGORICAL_FEATURES})
        rows.append(row)
    return pd.DataFrame(rows)


def test_churn_preprocessor_and_catboost_indices() -> None:
    preprocessor = ChurnPreprocessor()
    engineered = ChurnFeatureEngineer().transform(_minimal_frame())
    frame = preprocessor.fit_transform(engineered)

    assert frame[NUMERIC_FEATURES].isna().sum().sum() == 0
    assert frame["renewal_window"].iloc[0] in {"0_30_DAYS", "NO_ACTIVE_POLICY"}
    assert "UNKNOWN" in set(frame[CATEGORICAL_FEATURES].iloc[0])
    assert preprocessor.feature_columns == FEATURE_COLUMNS
    assert preprocessor.catboost_feature_indices() == list(
        range(len(NUMERIC_FEATURES), len(FEATURE_COLUMNS))
    )


def test_temporal_dataset_splitter_keeps_time_column() -> None:
    engineered = ChurnFeatureEngineer().transform(_minimal_frame())
    frame = ChurnPreprocessor().fit_transform(engineered)
    splits = TemporalDatasetSplitter().split(frame)

    assert set(splits) == {"train", "validation", "test", "backtest"}
    assert splits["train"].time.iloc[0] == "2023-12-31"
    assert "observation_date" in splits["train"].data.columns
    assert list(splits["train"].features.columns) == FEATURE_COLUMNS


def test_temporal_dataset_splitter_rejects_overlapping_time_windows() -> None:
    frame = ChurnFeatureEngineer().transform(_minimal_frame())
    frame = ChurnPreprocessor().fit_transform(frame)
    frame.loc[frame["split_name"] == "validation", "observation_date"] = "2022-12-31"

    try:
        TemporalDatasetSplitter().split(frame)
    except ValueError as exc:
        assert "Temporal leakage risk" in str(exc)
    else:
        raise AssertionError("Expected temporal leakage validation to fail")


def test_label_audit_columns_are_not_model_features() -> None:
    for column in LABEL_AUDIT_COLUMNS:
        assert column not in FEATURE_COLUMNS


def test_churn_preprocessor_requires_train_fit() -> None:
    preprocessor = ChurnPreprocessor()
    engineered = ChurnFeatureEngineer().transform(_minimal_frame())

    try:
        preprocessor.transform(engineered)
    except RuntimeError as exc:
        assert "fitted on the train split" in str(exc)
    else:
        raise AssertionError("Expected ChurnPreprocessor.transform to require fit first")


def test_binary_classifier_evaluator() -> None:
    evaluator = BinaryClassifierEvaluator(threshold=0.5)
    metrics = evaluator.evaluate(pd.Series([0, 1, 1, 0]), [0.1, 0.8, 0.7, 0.2])

    assert metrics["accuracy"] == 1.0
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0


def test_confusion_matrix_reporter_builds_matrix_frame() -> None:
    reporter = ConfusionMatrixReporter(threshold=0.5, size=(15, 6))
    matrix = reporter.matrix_frame(
        targets_by_split={"validation": pd.Series([0, 0, 1, 1])},
        probabilities_by_split={"validation": [0.1, 0.7, 0.4, 0.9]},
    )

    assert reporter.size == (15, 6)
    assert set(matrix.columns) == {"split_name", "actual_label", "predicted_label", "rows"}
    assert matrix["rows"].tolist() == [1, 1, 1, 1]


def test_class_distribution_plotter_builds_distribution_frame() -> None:
    plotter = ClassDistributionPlotter(size=(15, 6))
    distribution = plotter.distribution_frame(_minimal_frame())

    assert plotter.size == (15, 6)
    assert set(distribution.columns) == {
        "split_name",
        "churn_label",
        "rows",
        "total_rows",
        "share",
    }
    assert distribution["rows"].sum() == 4
    assert distribution["share"].sum() == 4.0
    assert distribution["split_name"].astype(str).drop_duplicates().tolist() == [
        "train",
        "validation",
        "backtest",
        "test",
    ]
