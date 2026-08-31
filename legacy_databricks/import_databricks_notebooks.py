#!/usr/bin/env python3
"""Import RetainFlow notebooks into the Databricks workspace."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]

NOTEBOOKS = [
    {
        "source": "data_engineering/23_run_phase1_pipeline_databricks.py",
        "target": "23_run_phase1_pipeline_databricks",
        "language": "PYTHON",
    },
    {
        "source": "notebooks/00_sql_explore_retainflow.sql",
        "target": "00_sql_explore_retainflow",
        "language": "SQL",
    },
    {
        "source": "churn_model/01_train_churn_model.py",
        "target": "01_train_churn_model",
        "language": "PYTHON",
    },
    {
        "source": "retention_engine/01_build_retention_priority_queue.py",
        "target": "01_build_retention_priority_queue",
        "language": "PYTHON",
    },
    {
        "source": "notebooks/02_retention_dashboard.sql",
        "target": "02_retention_dashboard",
        "language": "SQL",
    },
    {
        "source": "monitoring/01_monitoring_dashboard.sql",
        "target": "01_monitoring_dashboard",
        "language": "SQL",
    },
]

CONFIG_FILES = [
    {
        "source": "config/data_pipeline.yml",
        "target": "config/data_pipeline.yml",
    },
    {
        "source": "config/churn_model.yml",
        "target": "config/churn_model.yml",
    },
]

PACKAGE_FILES = [
    "retainflow/__init__.py",
    "retainflow/config.py",
    "retainflow/churn.py",
]

SQL_FILES = [
    "data_engineering/00_define_uc_model.sql",
    "data_engineering/02_seed_reference_dimensions.sql",
    "data_engineering/03_generate_customers.sql",
    "data_engineering/04_verify_customer_generation.sql",
    "data_engineering/05_generate_policies.sql",
    "data_engineering/06_verify_policy_generation.sql",
    "data_engineering/07_generate_payments.sql",
    "data_engineering/08_verify_payment_generation.sql",
    "data_engineering/09_generate_claims.sql",
    "data_engineering/10_verify_claim_generation.sql",
    "data_engineering/11_generate_interactions_service.sql",
    "data_engineering/12_verify_interactions_service_generation.sql",
    "data_engineering/13_generate_marketing_quotes.sql",
    "data_engineering/14_verify_marketing_quote_generation.sql",
    "data_engineering/15_generate_retention_actions.sql",
    "data_engineering/16_verify_retention_action_generation.sql",
    "data_engineering/17_build_gold_customer_360.sql",
    "data_engineering/18_verify_gold_customer_360.sql",
    "data_engineering/19_run_data_quality_checks.sql",
    "data_engineering/20_define_ml_model.sql",
    "data_engineering/20_verify_data_quality_results.sql",
    "data_engineering/21_build_ml_churn_dataset.sql",
    "data_engineering/22_verify_ml_churn_dataset.sql",
    "data_engineering/99_validate_data_architecture.sql",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import RetainFlow notebooks into Databricks Workspace."
    )
    parser.add_argument(
        "--profile",
        default="retainflow",
        help="Databricks CLI profile.",
    )
    parser.add_argument(
        "--workspace-dir",
        default="/Users/s239150.eps@gmail.com/RetainFlow",
        help="Databricks workspace directory where notebooks are imported.",
    )
    return parser.parse_args()


def run_command(command: list[str]) -> None:
    print("$ " + " ".join(command))
    subprocess.run(command, cwd=ROOT_DIR, check=True)


def main() -> int:
    args = parse_args()

    run_command(
        [
            "databricks",
            "workspace",
            "mkdirs",
            args.workspace_dir,
            "--profile",
            args.profile,
        ]
    )

    run_command(
        [
            "databricks",
            "workspace",
            "mkdirs",
            f"{args.workspace_dir.rstrip('/')}/data_engineering",
            "--profile",
            args.profile,
        ]
    )

    for sql_file in SQL_FILES:
        source = ROOT_DIR / sql_file
        if not source.exists():
            raise FileNotFoundError(source)

        target = f"{args.workspace_dir.rstrip('/')}/{sql_file}"
        run_command(
            [
                "databricks",
                "workspace",
                "import",
                str(source.relative_to(ROOT_DIR)),
                target,
                "--format",
                "AUTO",
                "--overwrite",
                "--profile",
                args.profile,
            ]
        )

    run_command(
        [
            "databricks",
            "workspace",
            "mkdirs",
            f"{args.workspace_dir.rstrip('/')}/config",
            "--profile",
            args.profile,
        ]
    )

    for config_file in CONFIG_FILES:
        source = ROOT_DIR / config_file["source"]
        if not source.exists():
            raise FileNotFoundError(source)

        target = f"{args.workspace_dir.rstrip('/')}/{config_file['target']}"
        run_command(
            [
                "databricks",
                "workspace",
                "import",
                str(source.relative_to(ROOT_DIR)),
                target,
                "--format",
                "AUTO",
                "--overwrite",
                "--profile",
                args.profile,
            ]
        )

    run_command(
        [
            "databricks",
            "workspace",
            "mkdirs",
            f"{args.workspace_dir.rstrip('/')}/retainflow",
            "--profile",
            args.profile,
        ]
    )

    for package_file in PACKAGE_FILES:
        source = ROOT_DIR / package_file
        if not source.exists():
            raise FileNotFoundError(source)

        target = f"{args.workspace_dir.rstrip('/')}/{package_file}"
        run_command(
            [
                "databricks",
                "workspace",
                "import",
                str(source.relative_to(ROOT_DIR)),
                target,
                "--format",
                "SOURCE",
                "--language",
                "PYTHON",
                "--overwrite",
                "--profile",
                args.profile,
            ]
        )

    for notebook in NOTEBOOKS:
        source = ROOT_DIR / notebook["source"]
        if not source.exists():
            raise FileNotFoundError(source)

        target = f"{args.workspace_dir.rstrip('/')}/{notebook['target']}"
        run_command(
            [
                "databricks",
                "workspace",
                "import",
                str(source.relative_to(ROOT_DIR)),
                target,
                "--format",
                "SOURCE",
                "--language",
                notebook["language"],
                "--overwrite",
                "--profile",
                args.profile,
            ]
        )

    print("\nNotebook import completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
