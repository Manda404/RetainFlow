"""Build the retention priority queue from churn predictions."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from retainflow.config import ChurnModelConfig, load_churn_model_config
from retainflow.logging import get_logger
from retainflow.retention.priority import (
    RetentionPriorityLoader,
    RetentionPriorityRepository,
    RetentionPriorityScorer,
)

logger = get_logger(__name__)


class RetentionQueuePipeline:
    """Orchestrate retention priority queue construction."""

    def __init__(
        self,
        config: ChurnModelConfig,
        loader: RetentionPriorityLoader | None = None,
        scorer: RetentionPriorityScorer | None = None,
        repository: RetentionPriorityRepository | None = None,
    ) -> None:
        self.config = config
        self.loader = loader or RetentionPriorityLoader(config)
        self.scorer = scorer or RetentionPriorityScorer()
        self.repository = repository or RetentionPriorityRepository(config)

    def run(
        self,
        split_names: tuple[str, ...] = ("test", "backtest"),
        save_postgres: bool = True,
    ) -> dict[str, Any]:
        candidates = self.loader.load(split_names=split_names)
        queue = self.scorer.score(candidates)
        queue_path = self.repository.save_csv(queue)
        if save_postgres:
            self.repository.save_postgres(queue)
        result = {
            "rows": len(queue),
            "queue_path": str(queue_path),
            "postgres_table": self.config.retention_queue_fqn if save_postgres else None,
            "top_priority": queue.head(10).to_dict(orient="records"),
        }
        logger.info("Retention queue complete: %s", result)
        return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the RetainFlow retention priority queue.")
    parser.add_argument(
        "--config",
        default="config/churn_model.yml",
        help="Path to the churn model YAML configuration.",
    )
    parser.add_argument(
        "--split",
        action="append",
        dest="splits",
        help="Split to include. Can be passed multiple times. Defaults to test and backtest.",
    )
    parser.add_argument(
        "--csv-only",
        action="store_true",
        help="Write the CSV artifact without updating PostgreSQL.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_churn_model_config(Path(args.config))
    splits = tuple(args.splits) if args.splits else ("test", "backtest")
    result = RetentionQueuePipeline(config).run(
        split_names=splits,
        save_postgres=not args.csv_only,
    )
    print(result)


if __name__ == "__main__":
    main()
