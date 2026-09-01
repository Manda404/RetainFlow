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
        feature_names: list[str] | None = None,
    ) -> None:
        self.config = config
        self.model = model
        self.evaluator = evaluator or BinaryClassifierEvaluator(config.prediction_threshold)
        self.feature_names = feature_names or FEATURE_COLUMNS

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

    def training_diagnostics(self) -> dict[str, float | int]:
        curve = self.training_curve()
        if curve.empty or "Logloss" not in set(curve["metric"]):
            return {}

        logloss = curve[curve["metric"] == "Logloss"]
        pivot = logloss.pivot(index="iteration", columns="dataset", values="value")
        diagnostics: dict[str, float | int] = {}
        if "validation" in pivot:
            best_iteration = int(pivot["validation"].idxmin())
            diagnostics["best_validation_iteration"] = best_iteration
            diagnostics["best_validation_logloss"] = float(pivot.loc[best_iteration, "validation"])
        if {"learn", "validation"} <= set(pivot.columns):
            final_iteration = int(pivot.index.max())
            diagnostics["final_iteration"] = final_iteration
            diagnostics["final_train_logloss"] = float(pivot.loc[final_iteration, "learn"])
            diagnostics["final_validation_logloss"] = float(pivot.loc[final_iteration, "validation"])
            diagnostics["final_logloss_gap_validation_minus_train"] = float(
                pivot.loc[final_iteration, "validation"] - pivot.loc[final_iteration, "learn"]
            )
        return diagnostics

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
        return ShapExplainer(model=self.model, feature_names=self.feature_names)


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
