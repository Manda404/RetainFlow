"""Configuration loading utilities for RetainFlow."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class ChurnModelConfig:
    catalog: str
    feature_schema: str
    feature_table: str
    label_table: str
    prediction_table: str
    experiment_name: str
    registered_model_name: str
    register_model: bool
    prediction_threshold: float
    iterations: int
    learning_rate: float
    depth: int

    @property
    def feature_fqn(self) -> str:
        return f"{self.catalog}.{self.feature_schema}.{self.feature_table}"

    @property
    def label_fqn(self) -> str:
        return f"{self.catalog}.{self.feature_schema}.{self.label_table}"

    @property
    def prediction_fqn(self) -> str:
        return f"{self.catalog}.{self.feature_schema}.{self.prediction_table}"


def load_yaml(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with config_path.open(encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def load_churn_model_config(path: str | Path) -> ChurnModelConfig:
    raw = load_yaml(path)
    return ChurnModelConfig(
        catalog=str(raw["catalog"]),
        feature_schema=str(raw["feature_schema"]),
        feature_table=str(raw["feature_table"]),
        label_table=str(raw["label_table"]),
        prediction_table=str(raw["prediction_table"]),
        experiment_name=str(raw["experiment_name"]),
        registered_model_name=str(raw["registered_model_name"]),
        register_model=bool(raw["register_model"]),
        prediction_threshold=float(raw["prediction_threshold"]),
        iterations=int(raw["iterations"]),
        learning_rate=float(raw["learning_rate"]),
        depth=int(raw["depth"]),
    )
