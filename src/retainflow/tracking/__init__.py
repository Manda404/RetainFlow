"""Tracking helpers for RetainFlow."""

from retainflow.tracking.runtime import configure_local_mlflow_runtime

__all__ = ["MLflowUIHandle", "configure_local_mlflow_runtime", "launch_mlflow_ui"]


def __getattr__(name: str):
    if name in {"MLflowUIHandle", "launch_mlflow_ui"}:
        from retainflow.tracking.mlflow_ui import MLflowUIHandle, launch_mlflow_ui

        return {"MLflowUIHandle": MLflowUIHandle, "launch_mlflow_ui": launch_mlflow_ui}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
