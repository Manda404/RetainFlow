"""Class-based PostgreSQL bootstrap workflow for RetainFlow."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import yaml
from sqlalchemy import create_engine, text

from retainflow.config import PROJECT_ROOT, resolve_project_path
from retainflow.data.csv_etl import generate_csv_dataset, load_csv_dataset_to_postgres
from retainflow.data.dataset import sqlalchemy_dsn
from retainflow.logging import get_logger


@dataclass(frozen=True)
class PostgresBootstrapConfig:
    """Configuration for the local CSV to PostgreSQL bootstrap pipeline."""

    n_customers: int
    seed: int
    csv_dir: Path
    dsn: str
    schema_name: str
    reset_database: bool
    docker_service_name: str


class PostgresBootstrapper:
    """Run each bootstrap step while keeping the notebook readable."""

    def __init__(self, config: PostgresBootstrapConfig, logger_name: str | None = None) -> None:
        self.config = config
        self.logger = get_logger(logger_name or __name__)

    def start_postgres_service(self) -> subprocess.CompletedProcess[str]:
        """Start the configured PostgreSQL Docker Compose service."""
        self.logger.info("Starting PostgreSQL Docker service: %s", self.config.docker_service_name)
        return subprocess.run(
            ["docker", "compose", "up", "-d", self.config.docker_service_name],
            check=True,
            capture_output=True,
            text=True,
        )

    def generate_csv_sources(self) -> Path:
        """Generate one CSV file per table before loading PostgreSQL."""
        self.logger.info(
            "Generating source CSV files: csv_dir=%s n_customers=%s seed=%s",
            self.config.csv_dir,
            self.config.n_customers,
            self.config.seed,
        )
        return generate_csv_dataset(
            self.config.csv_dir,
            n_customers=self.config.n_customers,
            seed=self.config.seed,
        )

    def load_csv_to_postgres(self, reset: bool | None = None) -> None:
        """Load generated CSV files into PostgreSQL in foreign-key dependency order."""
        reset_database = self.config.reset_database if reset is None else reset
        self.logger.info(
            "Loading CSV files into PostgreSQL: csv_dir=%s reset=%s",
            self.config.csv_dir,
            reset_database,
        )
        load_csv_dataset_to_postgres(
            self.config.csv_dir,
            dsn=self.config.dsn,
            reset=reset_database,
        )

    def table_volumes(self) -> pd.DataFrame:
        """Return core table row counts after loading."""
        tables = [
            "dim_customer",
            "dim_agency",
            "dim_agent",
            "fact_policy",
            "fact_payment",
            "fact_claim",
            "fact_interaction",
            "fact_customer_service",
            "fact_campaign_contact",
            "fact_quote",
            "fact_retention_action",
            "customer_360_snapshot",
            "churn_label",
        ]
        query = "\nUNION ALL\n".join(
            f"SELECT '{table}' AS table_name, count(*) AS rows FROM {self.config.schema_name}.{table}"
            for table in tables
        )
        engine = create_engine(sqlalchemy_dsn(self.config.dsn))
        with engine.connect() as conn:
            return pd.read_sql_query(f"{query}\nORDER BY table_name", conn)

    def split_distribution(self) -> pd.DataFrame:
        """Return row counts and churn rate by temporal split."""
        engine = create_engine(sqlalchemy_dsn(self.config.dsn))
        with engine.connect() as conn:
            return pd.read_sql_query(
                f"""
                SELECT
                    split_name,
                    count(*) AS rows,
                    sum(churn_label) AS churn_rows,
                    round(avg(churn_label)::numeric, 4) AS churn_rate
                FROM {self.config.schema_name}.churn_label
                GROUP BY split_name
                ORDER BY CASE split_name
                    WHEN 'train' THEN 1
                    WHEN 'validation' THEN 2
                    WHEN 'test' THEN 3
                    WHEN 'backtest' THEN 4
                    ELSE 5
                END
                """,
                conn,
            )

    def snapshot_feature_columns(self) -> pd.DataFrame:
        """Return the PostgreSQL columns available in the ML snapshot table."""
        engine = create_engine(sqlalchemy_dsn(self.config.dsn))
        with engine.connect() as conn:
            return pd.read_sql_query(
                text(
                    """
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = :schema_name
                  AND table_name = 'customer_360_snapshot'
                ORDER BY ordinal_position
                """
                ),
                conn,
                params={"schema_name": self.config.schema_name},
            )


def load_postgres_bootstrap_config(path: str | Path = "config/data_pipeline.yml") -> PostgresBootstrapConfig:
    """Load bootstrap settings from YAML and environment overrides."""
    config_path = Path(path)
    if not config_path.exists() and not config_path.is_absolute():
        config_path = PROJECT_ROOT / config_path
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    raw: dict[str, Any] = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    postgres = raw.get("postgres", {})
    docker = raw.get("docker", {})
    csv = raw.get("csv", {})

    dsn_env = str(postgres.get("dsn_env", "RETAINFLOW_POSTGRES_DSN"))
    default_dsn = str(
        postgres.get("default_dsn", "postgresql://retainflow:retainflow@localhost:55432/retainflow")
    )

    return PostgresBootstrapConfig(
        n_customers=int(os.getenv("RETAINFLOW_N_CUSTOMERS", raw.get("n_customers", 10000))),
        seed=int(os.getenv("RETAINFLOW_SEED", raw.get("seed", 42))),
        csv_dir=resolve_project_path(
            os.getenv("RETAINFLOW_CSV_DIR", str(csv.get("output_dir", "data/raw/retainflow_csv")))
        ),
        dsn=os.getenv(dsn_env, default_dsn),
        schema_name=str(postgres.get("schema", "retainflow")),
        reset_database=bool(raw.get("reset_database", True)),
        docker_service_name=str(docker.get("service_name", "postgres")),
    )
