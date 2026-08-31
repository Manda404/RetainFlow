"""Modeling visualizations."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from retainflow.features.preprocessing import SPLIT_COLUMN, TARGET_COLUMN

SPLIT_DISPLAY_ORDER = ("train", "validation", "backtest", "test")


class ClassDistributionPlotter:
    def __init__(
        self,
        split_column: str = SPLIT_COLUMN,
        target_column: str = TARGET_COLUMN,
        size: tuple[int, int] = (15, 6),
    ) -> None:
        self.split_column = split_column
        self.target_column = target_column
        self.size = size

    def distribution_frame(self, dataset: pd.DataFrame) -> pd.DataFrame:
        counts = (
            dataset.groupby([self.split_column, self.target_column], dropna=False)
            .size()
            .rename("rows")
            .reset_index()
        )
        counts["total_rows"] = counts.groupby(self.split_column)["rows"].transform("sum")
        counts["share"] = counts["rows"] / counts["total_rows"]
        counts[self.split_column] = pd.Categorical(
            counts[self.split_column],
            categories=SPLIT_DISPLAY_ORDER,
            ordered=True,
        )
        return counts.sort_values([self.split_column, self.target_column]).reset_index(drop=True)

    def plot(self, dataset: pd.DataFrame, path: str | Path | None = None):
        import matplotlib.pyplot as plt

        distribution = self.distribution_frame(dataset)
        plot_data = distribution.pivot(
            index=self.split_column,
            columns=self.target_column,
            values="rows",
        ).fillna(0)
        ordered_splits = [split for split in SPLIT_DISPLAY_ORDER if split in plot_data.index]
        plot_data = plot_data.reindex(ordered_splits)

        ax = plot_data.plot(kind="bar", figsize=self.size, width=0.78)
        ax.set_title("Distribution des classes par sous-dataset")
        ax.set_xlabel("Sous-dataset")
        ax.set_ylabel("Nombre de lignes")
        ax.legend(title=self.target_column)
        ax.tick_params(axis="x", rotation=0)
        ax.set_ylim(top=max(plot_data.max().max() * 1.12, 1))

        share_lookup = {
            (row[self.split_column], row[self.target_column]): row["share"]
            for _, row in distribution.iterrows()
        }
        for container, class_label in zip(ax.containers, plot_data.columns, strict=True):
            labels = []
            for patch, split_name in zip(container, plot_data.index, strict=True):
                rows = int(patch.get_height())
                share = share_lookup.get((split_name, class_label), 0.0)
                labels.append(f"{rows}\n{share:.1%}")
            ax.bar_label(container, labels=labels, padding=3, fontsize=9)

        plt.tight_layout()
        if path is not None:
            output_path = Path(path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(output_path, dpi=160, bbox_inches="tight")
        return ax
