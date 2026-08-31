"""Temporal split helpers."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from retainflow.features.preprocessing import (
    FEATURE_COLUMNS,
    ID_COLUMNS,
    SPLIT_COLUMN,
    TARGET_COLUMN,
)


@dataclass(frozen=True)
class DatasetSplit:
    data: pd.DataFrame
    features: pd.DataFrame
    target: pd.Series
    time: pd.Series


class TemporalDatasetSplitter:
    def __init__(
        self,
        split_names: list[str] | None = None,
        feature_columns: list[str] | None = None,
        target_column: str = TARGET_COLUMN,
        split_column: str = SPLIT_COLUMN,
        time_column: str = "observation_date",
    ) -> None:
        self.split_names = split_names or ["train", "validation", "test", "backtest"]
        self.feature_columns = feature_columns or FEATURE_COLUMNS
        self.target_column = target_column
        self.split_column = split_column
        self.time_column = time_column

    def split(self, frame: pd.DataFrame) -> dict[str, DatasetSplit]:
        self.validate_temporal_order(frame)
        splits = {}
        for split_name in self.split_names:
            subset = frame.loc[frame[self.split_column] == split_name].copy()
            split_columns = ID_COLUMNS + [self.split_column] + self.feature_columns + [self.target_column]
            splits[split_name] = DatasetSplit(
                data=subset[split_columns],
                features=subset[self.feature_columns],
                target=subset[self.target_column],
                time=subset[self.time_column],
            )
        return splits

    def validate_temporal_order(self, frame: pd.DataFrame) -> None:
        bounds = (
            frame.groupby(self.split_column)[self.time_column]
            .agg(["min", "max"])
            .reindex(self.split_names)
        )
        if bounds[["min", "max"]].isna().any().any():
            missing = bounds[bounds["min"].isna()].index.tolist()
            raise ValueError(f"Missing expected temporal splits: {missing}")

        previous_max = None
        for split_name, row in bounds.iterrows():
            current_min = row["min"]
            current_max = row["max"]
            if previous_max is not None and current_min <= previous_max:
                raise ValueError(
                    "Temporal leakage risk: split "
                    f"{split_name} starts at {current_min}, before or at previous max {previous_max}."
                )
            previous_max = current_max

    def class_distribution(self, frame: pd.DataFrame) -> pd.DataFrame:
        distribution = (
            frame.groupby([self.split_column, self.target_column], dropna=False)
            .size()
            .rename("rows")
            .reset_index()
        )
        distribution["total_rows"] = distribution.groupby(self.split_column)["rows"].transform("sum")
        distribution["share"] = distribution["rows"] / distribution["total_rows"]
        return distribution.sort_values([self.split_column, self.target_column]).reset_index(drop=True)


def split_dataset(frame: pd.DataFrame) -> dict[str, DatasetSplit]:
    return TemporalDatasetSplitter().split(frame)
