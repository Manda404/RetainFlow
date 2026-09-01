"""Evaluation metrics and diagnostic plots."""

from retainflow.evaluation.drift import DriftAnalyzer, DriftDashboardBuilder, DriftThresholds
from retainflow.evaluation.leakage import DataLeakageAuditor, LeakageFinding
from retainflow.evaluation.metrics import (
    BinaryClassifierEvaluator,
    ConfusionMatrixReporter,
    ThresholdTradeoffAnalyzer,
)
from retainflow.evaluation.visualization import ClassDistributionPlotter

__all__ = [
    "BinaryClassifierEvaluator",
    "ClassDistributionPlotter",
    "ConfusionMatrixReporter",
    "ThresholdTradeoffAnalyzer",
    "DriftAnalyzer",
    "DriftDashboardBuilder",
    "DriftThresholds",
    "DataLeakageAuditor",
    "LeakageFinding",
]
