from pathlib import Path

import pandas as pd

from retainflow.data.splitting import TemporalDatasetSplitter
from retainflow.evaluation.drift import DriftAnalyzer, DriftDashboardBuilder
from retainflow.evaluation.leakage import DataLeakageAuditor
from retainflow.evaluation.metrics import (
    BinaryClassifierEvaluator,
    ConfusionMatrixReporter,
    ThresholdTradeoffAnalyzer,
)
from retainflow.evaluation.visualization import ClassDistributionPlotter
from retainflow.features.engineering import LABEL_AUDIT_COLUMNS, ChurnFeatureEngineer
from retainflow.features.preprocessing import (
    CATEGORICAL_FEATURES,
    FEATURE_COLUMNS,
    NUMERIC_FEATURES,
    ChurnPreprocessor,
)
from retainflow.features.selection import DriftFeatureSelector
from retainflow.pipelines.drift_dashboard import ChurnDriftDashboardPipeline


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


def test_data_leakage_auditor_rejects_forbidden_model_features() -> None:
    auditor = DataLeakageAuditor()
    report = auditor.audit(
        _minimal_frame(),
        feature_columns=["tenure_months", "latent_churn_risk_band"],
    )
    finding = report.set_index("check_name").loc["forbidden_features_not_in_model_contract"]

    assert finding["status"] == "failed"
    assert finding["severity"] == "critical"
    assert finding["details"]["forbidden_features_found"] == ["latent_churn_risk_band"]


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


def test_threshold_tradeoff_analyzer_builds_grid_and_best_threshold() -> None:
    analyzer = ThresholdTradeoffAnalyzer(thresholds=[0.2, 0.5, 0.8], beta=2.0, size=(15, 6))
    grid = analyzer.grid_frame(
        y_true=pd.Series([0, 0, 1, 1]),
        probabilities=[0.1, 0.4, 0.7, 0.9],
    )

    assert analyzer.size == (15, 6)
    assert set(
        [
            "threshold",
            "true_non_churn",
            "false_alarms",
            "churn_missed",
            "churn_detected",
            "precision",
            "recall",
            "f2",
            "alert_rate",
        ]
    ) <= set(grid.columns)
    assert grid.loc[grid["threshold"] == 0.5, "churn_detected"].iloc[0] == 2
    assert analyzer.best_threshold(grid) == 0.5


def test_threshold_tradeoff_analyzer_default_threshold_range() -> None:
    analyzer = ThresholdTradeoffAnalyzer()

    assert analyzer.thresholds[0] == 0.02
    assert analyzer.thresholds[-1] == 0.38
    assert len(analyzer.thresholds) == 10



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


def test_drift_analyzer_detects_numeric_and_target_drift() -> None:
    frame = pd.DataFrame(
        {
            "split_name": ["train"] * 6 + ["test"] * 6,
            "tenure_months": [10, 11, 12, 13, 14, 15, 80, 82, 84, 86, 88, 90],
            "customer_segment": ["A", "A", "A", "B", "B", "B", "A", "C", "C", "C", "C", "C"],
            "churn_label": [0, 0, 0, 1, 0, 0, 1, 1, 1, 1, 0, 1],
        }
    )
    analyzer = DriftAnalyzer(
        feature_columns=["tenure_months", "customer_segment"],
        numeric_features=["tenure_months"],
        categorical_features=["customer_segment"],
        split_order=("train", "test"),
    )

    report = analyzer.analyze(frame)
    summary = analyzer.summary(report)

    assert {"tenure_months", "customer_segment", "churn_label"} <= set(report["feature"])
    assert summary["total_comparisons"] == 1
    assert summary["high_drift_features"] >= 1


def test_drift_dashboard_builder_writes_html(tmp_path) -> None:
    report = pd.DataFrame(
        [
            {
                "reference_split": "train",
                "comparison_split": "test",
                "feature": "tenure_months",
                "feature_type": "numeric",
                "psi": 0.3,
                "secondary_metric_name": "ks_statistic",
                "secondary_metric": 0.2,
                "secondary_pvalue": 0.01,
                "reference_missing_rate": 0.0,
                "comparison_missing_rate": 0.0,
                "missing_rate_delta": 0.0,
                "reference_mean": 10.0,
                "comparison_mean": 30.0,
                "reference_top_value": "",
                "comparison_top_value": "",
                "severity": "high",
                "severity_rank": 3,
                "is_reference_comparison": True,
            }
        ]
    )
    summary = {
        "total_comparisons": 1,
        "total_features": 1,
        "high_drift_features": 1,
        "moderate_drift_features": 0,
        "stable_features": 0,
        "top_drift_features": [],
    }

    output = DriftDashboardBuilder().save(
        report,
        summary,
        dashboard_path=tmp_path / "dashboard.html",
        summary_path=tmp_path / "summary.json",
    )

    assert output.exists()
    assert "Dashboard de drift" in output.read_text(encoding="utf-8")
    assert (tmp_path / "summary.json").exists()


def test_churn_drift_pipeline_orchestrates_steps(tmp_path) -> None:
    class Config:
        drift_report_path = tmp_path / "drift.csv"
        drift_summary_path = tmp_path / "summary.json"
        drift_dashboard_path = tmp_path / "dashboard.html"

    class Loader:
        def load(self):
            return pd.DataFrame(
                {
                    "split_name": ["train", "train", "test", "test"],
                    "tenure_months": [10, 12, 40, 42],
                    "customer_segment": ["A", "A", "B", "B"],
                    "churn_label": [0, 0, 1, 1],
                }
            )

    class FeatureEngineer:
        def transform(self, raw_dataset):
            return raw_dataset

    analyzer = DriftAnalyzer(
        feature_columns=["tenure_months", "customer_segment"],
        numeric_features=["tenure_months"],
        categorical_features=["customer_segment"],
        split_order=("train", "test"),
    )
    pipeline = ChurnDriftDashboardPipeline(
        config=Config(),  # type: ignore[arg-type]
        loader=Loader(),  # type: ignore[arg-type]
        feature_engineer=FeatureEngineer(),  # type: ignore[arg-type]
        analyzer=analyzer,
        dashboard_builder=DriftDashboardBuilder(),
    )

    result = pipeline.run()

    assert Path(result["drift_report_path"]).exists()
    assert Path(result["drift_summary_path"]).exists()
    assert Path(result["drift_dashboard_path"]).exists()


def test_drift_feature_selector_builds_exclusion_json(tmp_path) -> None:
    drift_report = pd.DataFrame(
        [
            {
                "reference_split": "train",
                "comparison_split": "test",
                "feature": "tenure_months",
                "feature_type": "numeric",
                "psi": 0.5,
                "secondary_metric_name": "ks_statistic",
                "secondary_metric": 0.4,
                "missing_rate_delta": 0.0,
                "severity": "high",
                "severity_rank": 3,
                "is_reference_comparison": True,
            },
            {
                "reference_split": "train",
                "comparison_split": "test",
                "feature": "observation_year",
                "feature_type": "numeric",
                "psi": 1.0,
                "secondary_metric_name": "ks_statistic",
                "secondary_metric": 1.0,
                "missing_rate_delta": 0.0,
                "severity": "high",
                "severity_rank": 3,
                "is_reference_comparison": True,
            },
        ]
    )
    raw_dataset = pd.DataFrame(
        {
            "observation_date": ["2024-12-31"],
            "customer_id": ["CUST-1"],
            "split_name": ["train"],
            "tenure_months": [12],
            "churn_label": [0],
        }
    )

    selector = DriftFeatureSelector(drift_report)
    selection = selector.build_selection(raw_dataset)
    output = selector.save_selection(selection, tmp_path / "drift_feature_exclusions.json")

    assert "tenure_months" in selection.raw_columns_to_drop
    assert "observation_year" in selection.excluded_engineered_features
    assert "latent_churn_risk_band" in selection.features_to_remove
    assert "tenure_months" not in selection.selected_feature_columns
    assert "latent_churn_risk_band" not in selection.selected_feature_columns
    assert output.exists()
