"""Build the RetainFlow drift dashboard."""

from __future__ import annotations

import argparse
from typing import Any

from retainflow.config import ChurnModelConfig, load_churn_model_config
from retainflow.data.dataset import ChurnDatasetLoader
from retainflow.evaluation.drift import DriftAnalyzer, DriftDashboardBuilder
from retainflow.features.engineering import ChurnFeatureEngineer
from retainflow.logging import get_logger

logger = get_logger(__name__)


class ChurnDriftDashboardPipeline:
    """Step-by-step drift dashboard workflow for notebooks and CLI."""

    def __init__(
        self,
        config: ChurnModelConfig,
        loader: ChurnDatasetLoader | None = None,
        feature_engineer: ChurnFeatureEngineer | None = None,
        analyzer: DriftAnalyzer | None = None,
        dashboard_builder: DriftDashboardBuilder | None = None,
    ) -> None:
        self.config = config
        self.loader = loader or ChurnDatasetLoader(config)
        self.feature_engineer = feature_engineer or ChurnFeatureEngineer()
        self.analyzer = analyzer or DriftAnalyzer()
        self.dashboard_builder = dashboard_builder or DriftDashboardBuilder()

    def load_raw_dataset(self):
        logger.info("Loading raw churn dataset for drift analysis")
        return self.loader.load()

    def build_feature_dataset(self, raw_dataset):
        logger.info("Building drift feature dataset")
        return self.feature_engineer.transform(raw_dataset)

    def analyze(self, dataset):
        logger.info("Analyzing drift across dataset splits")
        drift_report = self.analyzer.analyze(dataset)
        summary = self.analyzer.summary(drift_report)
        return drift_report, summary

    def save(self, drift_report, summary: dict[str, Any]) -> dict[str, Any]:
        self.config.drift_report_path.parent.mkdir(parents=True, exist_ok=True)
        drift_report.to_csv(self.config.drift_report_path, index=False)
        dashboard_path = self.dashboard_builder.save(
            drift_report=drift_report,
            summary=summary,
            dashboard_path=self.config.drift_dashboard_path,
            summary_path=self.config.drift_summary_path,
        )
        logger.info("Drift dashboard saved to %s", dashboard_path)
        return {
            "drift_report_path": str(self.config.drift_report_path),
            "drift_summary_path": str(self.config.drift_summary_path),
            "drift_dashboard_path": str(dashboard_path),
            "summary": summary,
        }

    def run(self) -> dict[str, Any]:
        logger.info("Building drift dashboard")
        raw_dataset = self.load_raw_dataset()
        dataset = self.build_feature_dataset(raw_dataset)
        drift_report, summary = self.analyze(dataset)
        return self.save(drift_report, summary)


def build_drift_dashboard(config: ChurnModelConfig) -> dict[str, Any]:
    return ChurnDriftDashboardPipeline(config).run()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the RetainFlow drift dashboard.")
    parser.add_argument(
        "--config",
        default="config/churn_model.yml",
        help="Path to the churn model YAML configuration.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_churn_model_config(args.config)
    result = build_drift_dashboard(config)
    print(result["drift_dashboard_path"])


if __name__ == "__main__":
    main()
