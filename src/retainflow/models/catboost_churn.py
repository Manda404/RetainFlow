"""CatBoost model utilities for churn prediction."""

from __future__ import annotations

from importlib.metadata import version

import pandas as pd
from catboost import CatBoostClassifier, Pool

from retainflow.config import ChurnModelConfig
from retainflow.evaluation.metrics import BinaryClassifierEvaluator
from retainflow.explainability.shap import ShapExplainer
from retainflow.features.preprocessing import FEATURE_COLUMNS
from retainflow.logging import get_logger

logger = get_logger(__name__)


class ChurnModelTrainer:
    """Class-based CatBoost workflow for churn model development."""

    def __init__(
        self,
        config: ChurnModelConfig,
        model: CatBoostClassifier,
        evaluator: BinaryClassifierEvaluator | None = None,
    ) -> None:
        self.config = config
        self.model = model
        self.evaluator = evaluator or BinaryClassifierEvaluator(config.prediction_threshold)

    def fit(self, train_pool: Pool, valid_pool: Pool) -> CatBoostClassifier:
        self.model.fit(train_pool, eval_set=valid_pool, use_best_model=True)
        return self.model

    def evaluation_history(self) -> dict[str, dict[str, list[float]]]:
        return self.model.get_evals_result()

    def training_curve(self) -> pd.DataFrame:
        rows = []
        for dataset_name, metrics in self.evaluation_history().items():
            for metric_name, values in metrics.items():
                rows.extend(
                    {
                        "iteration": iteration,
                        "dataset": dataset_name,
                        "metric": metric_name,
                        "value": float(value),
                    }
                    for iteration, value in enumerate(values, start=1)
                )
        return pd.DataFrame(rows)

    def evaluate(
        self,
        pools_by_split: dict[str, Pool],
        targets_by_split: dict[str, pd.Series],
    ) -> tuple[dict[str, dict[str, float]], dict[str, list[float]]]:
        metrics_by_split = {}
        probabilities_by_split = {}

        for split_name, pool in pools_by_split.items():
            probabilities = predict_positive_class_probability(self.model, pool)
            probabilities_by_split[split_name] = probabilities
            metrics = self.evaluator.evaluate(targets_by_split[split_name], probabilities)
            metrics_by_split[split_name] = metrics
            logger.info("%s metrics: %s", split_name, metrics)

        return metrics_by_split, probabilities_by_split

    def shap_summary(self, train_pool: Pool, sample_size: int = 1000) -> pd.DataFrame:
        return self.shap_explainer().summary_frame(train_pool, sample_size=sample_size)

    def shap_explainer(self) -> ShapExplainer:
        return ShapExplainer(model=self.model, feature_names=FEATURE_COLUMNS)


def shap_version() -> str:
    return version("shap")


def predict_positive_class_probability(model: CatBoostClassifier, pool: Pool) -> list[float]:
    return model.predict_proba(pool)[:, 1].tolist()


def build_shap_summary(
    model: CatBoostClassifier, train_pool: Pool, sample_size: int = 1000
) -> pd.DataFrame:
    return ShapExplainer(model=model, feature_names=FEATURE_COLUMNS).summary_frame(
        train_pool,
        sample_size=sample_size,
    )
