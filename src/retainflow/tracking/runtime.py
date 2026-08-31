"""Local MLflow runtime guardrails."""

from __future__ import annotations

import logging
import os
import warnings


def configure_local_mlflow_runtime() -> None:
    """Keep RetainFlow's MLflow usage local and quiet about Databricks integrations."""
    os.environ.setdefault("MLFLOW_ENABLE_SYSTEM_METRICS_LOGGING", "true")
    warnings.filterwarnings(
        "ignore",
        message=r"\s*To use databricks widgets interactively.*",
        category=UserWarning,
        module=r"databricks\.sdk\._widgets.*",
    )
    warnings.filterwarnings(
        "ignore",
        message=r"Hint: Inferred schema contains integer column.*",
        category=UserWarning,
        module=r"mlflow\.types\.utils",
    )
    logging.getLogger("databricks").setLevel(logging.ERROR)
    logging.getLogger("databricks.sdk").setLevel(logging.ERROR)
