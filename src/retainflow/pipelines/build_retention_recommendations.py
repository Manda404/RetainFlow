"""Build human-reviewable retention recommendations."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from retainflow.config import ChurnModelConfig, load_churn_model_config
from retainflow.logging import get_logger
from retainflow.retention.strategy import (
    RetentionRecommendationRepository,
    RetentionStrategyEngine,
    RetentionStrategyLoader,
)

logger = get_logger(__name__)


class RetentionRecommendationPipeline:
    """Orchestrate retention strategy recommendations."""

    def __init__(
        self,
        config: ChurnModelConfig,
        loader: RetentionStrategyLoader | None = None,
        engine: RetentionStrategyEngine | None = None,
        repository: RetentionRecommendationRepository | None = None,
    ) -> None:
        self.config = config
        self.loader = loader or RetentionStrategyLoader(config)
        self.engine = engine or RetentionStrategyEngine()
        self.repository = repository or RetentionRecommendationRepository(config)

    def run(
        self,
        limit: int = 500,
        save_postgres: bool = True,
    ) -> dict[str, Any]:
        priority_queue = self.loader.load(limit=limit)
        recommendations = self.engine.recommend(priority_queue)
        recommendation_path = self.repository.save_csv(recommendations)
        if save_postgres:
            self.repository.save_postgres(recommendations)
        result = {
            "rows": len(recommendations),
            "recommendation_path": str(recommendation_path),
            "postgres_table": self.config.retention_recommendation_fqn if save_postgres else None,
            "top_recommendations": recommendations.head(10).to_dict(orient="records"),
        }
        logger.info("Retention recommendations complete: %s", result)
        return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build RetainFlow retention recommendations.")
    parser.add_argument(
        "--config",
        default="config/churn_model.yml",
        help="Path to the churn model YAML configuration.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=500,
        help="Maximum number of prioritized customers to convert into recommendations.",
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
    result = RetentionRecommendationPipeline(config).run(
        limit=args.limit,
        save_postgres=not args.csv_only,
    )
    print(result)


if __name__ == "__main__":
    main()
