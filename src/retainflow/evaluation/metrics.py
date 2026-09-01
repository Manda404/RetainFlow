"""Model evaluation utilities."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


class BinaryClassifierEvaluator:
    def __init__(self, threshold: float) -> None:
        self.threshold = threshold

    def evaluate(self, y_true: pd.Series, probabilities: list[float]) -> dict[str, float]:
        predictions = [1 if probability >= self.threshold else 0 for probability in probabilities]
        metrics = {
            "accuracy": float(accuracy_score(y_true, predictions)),
            "f1": float(f1_score(y_true, predictions, zero_division=0)),
            "precision": float(precision_score(y_true, predictions, zero_division=0)),
            "recall": float(recall_score(y_true, predictions, zero_division=0)),
            "average_precision": float(average_precision_score(y_true, probabilities)),
        }
        metrics["auc"] = float(roc_auc_score(y_true, probabilities)) if y_true.nunique() > 1 else 0.0
        return metrics


class ConfusionMatrixReporter:
    """Build and plot confusion matrices for each evaluation split."""

    def __init__(
        self,
        threshold: float,
        size: tuple[int, int] = (15, 6),
        split_order: tuple[str, ...] = ("test", "backtest"),
        negative_label: str = "pas churn",
        positive_label: str = "churn",
    ) -> None:
        self.threshold = threshold
        self.size = size
        self.split_order = split_order
        self.negative_label = negative_label
        self.positive_label = positive_label

    def matrix_frame(
        self,
        targets_by_split: dict[str, pd.Series],
        probabilities_by_split: dict[str, list[float]],
    ) -> pd.DataFrame:
        rows = []
        for split_name, y_true in targets_by_split.items():
            probabilities = probabilities_by_split[split_name]
            predictions = [1 if probability >= self.threshold else 0 for probability in probabilities]
            matrix = confusion_matrix(y_true, predictions, labels=[0, 1])
            for actual_label in (0, 1):
                for predicted_label in (0, 1):
                    rows.append(
                        {
                            "split_name": split_name,
                            "actual_label": actual_label,
                            "predicted_label": predicted_label,
                            "rows": int(matrix[actual_label, predicted_label]),
                        }
                    )
        return pd.DataFrame(rows)

    def plot(self, matrix_frame: pd.DataFrame, path=None):
        import matplotlib.pyplot as plt
        from matplotlib.patches import Rectangle

        available_splits = [
            split_name
            for split_name in self.split_order
            if split_name in set(matrix_frame["split_name"].astype(str))
        ]
        if not available_splits:
            raise ValueError("No supported split found for confusion matrix plotting.")
        figure, axes = plt.subplots(1, len(available_splits), figsize=self.size, layout="constrained")
        if len(available_splits) == 1:
            axes = [axes]

        for ax, split_name in zip(axes, available_splits, strict=True):
            subset = matrix_frame[matrix_frame["split_name"] == split_name]
            matrix = (
                subset.pivot(index="actual_label", columns="predicted_label", values="rows")
                .reindex(index=[0, 1], columns=[0, 1])
                .fillna(0)
                .astype(int)
            )
            false_positives = int(matrix.loc[0, 1])
            false_negatives = int(matrix.loc[1, 0])
            true_positives = int(matrix.loc[1, 1])
            total = max(int(matrix.values.sum()), 1)
            precision = true_positives / max(true_positives + false_positives, 1)
            recall = true_positives / max(true_positives + false_negatives, 1)

            ax.set_xlim(0, 2)
            ax.set_ylim(2, 0)
            ax.set_aspect("equal")
            ax.set_facecolor("#F8FAFC")
            ax.set_title(
                f"{split_name}\nprecision churn {precision:.1%} | rappel churn {recall:.1%}",
                fontsize=12,
                pad=12,
            )
            ax.set_xlabel("Prediction", labelpad=10)
            ax.set_ylabel("Reel", labelpad=10)
            ax.set_xticks([0.5, 1.5], labels=[self.negative_label, self.positive_label])
            ax.set_yticks([0.5, 1.5], labels=[self.negative_label, self.positive_label])
            ax.tick_params(which="major", bottom=False, left=False)
            for spine in ax.spines.values():
                spine.set_visible(False)

            cell_styles = {
                (0, 0): ("TN", "#D1FAE5", "#065F46"),
                (0, 1): ("FP", "#FEF3C7", "#92400E"),
                (1, 0): ("FN", "#FEE2E2", "#991B1B"),
                (1, 1): ("TP", "#BFDBFE", "#1E3A8A"),
            }
            row_totals = matrix.sum(axis=1).replace(0, 1)
            for actual_label in (0, 1):
                for predicted_label in (0, 1):
                    value = int(matrix.loc[actual_label, predicted_label])
                    code, face_color, text_color = cell_styles[(actual_label, predicted_label)]
                    row_share = value / int(row_totals.loc[actual_label])
                    total_share = value / total
                    ax.add_patch(
                        Rectangle(
                            (predicted_label, actual_label),
                            1,
                            1,
                            facecolor=face_color,
                            edgecolor="white",
                            linewidth=3,
                        )
                    )
                    ax.text(
                        predicted_label + 0.5,
                        actual_label + 0.38,
                        code,
                        ha="center",
                        va="center",
                        color=text_color,
                        fontsize=11,
                        fontweight="bold",
                    )
                    ax.text(
                        predicted_label + 0.5,
                        actual_label + 0.56,
                        f"{value:,}".replace(",", " "),
                        ha="center",
                        va="center",
                        color="#111827",
                        fontsize=15,
                        fontweight="bold",
                    )
                    ax.text(
                        predicted_label + 0.5,
                        actual_label + 0.72,
                        f"{row_share:.1%} ligne | {total_share:.1%} total",
                        ha="center",
                        va="center",
                        color="#4B5563",
                        fontsize=9,
                    )

        figure.suptitle("Matrice de confusion - churn", fontsize=16, fontweight="bold")
        if path is not None:
            output_path = Path(path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            figure.savefig(output_path, dpi=160, bbox_inches="tight")
        return figure


def evaluate_binary_classifier(
    y_true: pd.Series,
    probabilities: list[float],
    threshold: float,
) -> dict[str, float]:
    return BinaryClassifierEvaluator(threshold).evaluate(y_true, probabilities)


class ThresholdTradeoffAnalyzer:
    """Analyze the precision/recall trade-off across decision thresholds."""

    def __init__(
        self,
        thresholds: list[float] | None = None,
        beta: float = 2.0,
        size: tuple[int, int] = (15, 6),
        positive_label: str = "churn",
    ) -> None:
        self.thresholds = thresholds or np.round(np.arange(0.02, 0.42, 0.04), 3).tolist()
        self.beta = beta
        self.size = size
        self.positive_label = positive_label

    def grid_frame(
        self,
        y_true: pd.Series,
        probabilities: list[float] | np.ndarray,
    ) -> pd.DataFrame:
        proba = np.asarray(probabilities)
        rows = []
        true_positive_rate = float(pd.Series(y_true).mean())
        for threshold in self.thresholds:
            predictions = (proba >= threshold).astype(int)
            tn, fp, fn, tp = confusion_matrix(y_true, predictions, labels=[0, 1]).ravel()
            precision = tp / (tp + fp) if (tp + fp) else 0.0
            recall = tp / (tp + fn) if (tp + fn) else 0.0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
            beta_squared = self.beta**2
            fbeta = (
                (1 + beta_squared) * precision * recall / (beta_squared * precision + recall)
                if (precision + recall)
                else 0.0
            )
            rows.append(
                {
                    "threshold": float(threshold),
                    "true_non_churn": int(tn),
                    "false_alarms": int(fp),
                    f"{self.positive_label}_missed": int(fn),
                    f"{self.positive_label}_detected": int(tp),
                    "precision": round(float(precision), 3),
                    "recall": round(float(recall), 3),
                    "f1": round(float(f1), 3),
                    f"f{self.beta:g}": round(float(fbeta), 3),
                    "alert_rate": round(float(predictions.mean()), 3),
                    "true_positive_rate": round(true_positive_rate, 3),
                }
            )
        return pd.DataFrame(rows)

    def best_threshold(self, grid: pd.DataFrame) -> float:
        score_column = f"f{self.beta:g}"
        best_row = grid.sort_values(
            [score_column, "recall", "precision"],
            ascending=[False, False, False],
        ).iloc[0]
        return float(best_row["threshold"])

    def plot(
        self,
        grid: pd.DataFrame,
        best_threshold: float | None = None,
        path: str | Path | None = None,
    ):
        import matplotlib.pyplot as plt

        active_best_threshold = best_threshold if best_threshold is not None else self.best_threshold(grid)
        figure, ax = plt.subplots(figsize=self.size)
        ax.plot(
            grid["threshold"],
            grid["recall"],
            marker="o",
            color="#C44E52",
            label=f"Recall ({self.positive_label} detected)",
        )
        ax.plot(
            grid["threshold"],
            grid["precision"],
            marker="s",
            color="#4C72B0",
            label="Precision (alerts that were real)",
        )
        ax.axvline(
            active_best_threshold,
            color="black",
            ls="--",
            label=f"tuned threshold = {active_best_threshold:.3f}",
        )
        ax.set_xlabel("Decision threshold")
        ax.set_ylabel("Score")
        ax.set_title("Precision/recall trade-off controlled by the decision threshold")
        ax.set_ylim(0, 1.05)
        ax.grid(axis="y", color="#E5E7EB", linewidth=0.8)
        ax.legend()
        plt.tight_layout()
        if path is not None:
            output_path = Path(path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            figure.savefig(output_path, dpi=160, bbox_inches="tight")
        return figure
