#!/usr/bin/env python3
"""Run the RetainFlow Phase 1 Databricks SQL pipeline.

The runner uses the Databricks CLI so it can reuse the local profile already
configured with `databricks auth login`.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[1]
SQL_DIR = ROOT_DIR / "data_engineering"

PIPELINE_FILES = [
    "00_define_uc_model.sql",
    "02_seed_reference_dimensions.sql",
    "03_generate_customers.sql",
    "05_generate_policies.sql",
    "07_generate_payments.sql",
    "09_generate_claims.sql",
    "11_generate_interactions_service.sql",
    "13_generate_marketing_quotes.sql",
    "15_generate_retention_actions.sql",
    "17_build_gold_customer_360.sql",
    "20_define_ml_model.sql",
    "21_build_ml_churn_dataset.sql",
    "19_run_data_quality_checks.sql",
]

VALIDATION_FILES = [
    "04_verify_customer_generation.sql",
    "06_verify_policy_generation.sql",
    "08_verify_payment_generation.sql",
    "10_verify_claim_generation.sql",
    "12_verify_interactions_service_generation.sql",
    "14_verify_marketing_quote_generation.sql",
    "16_verify_retention_action_generation.sql",
    "18_verify_gold_customer_360.sql",
    "22_verify_ml_churn_dataset.sql",
    "20_verify_data_quality_results.sql",
    "99_validate_data_architecture.sql",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the RetainFlow Phase 1 SQL pipeline on Databricks."
    )
    parser.add_argument(
        "--profile",
        default=os.getenv("DATABRICKS_CONFIG_PROFILE", "retainflow"),
        help="Databricks CLI profile to use.",
    )
    parser.add_argument(
        "--warehouse-id",
        default=os.getenv("DATABRICKS_SQL_WAREHOUSE_ID"),
        help="SQL Warehouse ID.",
    )
    parser.add_argument(
        "--n-customers",
        type=int,
        default=int(os.getenv("RETAINFLOW_N_CUSTOMERS", "10000")),
        help="Number of customers to generate.",
    )
    parser.add_argument(
        "--history-start-date",
        default="2021-01-01",
        help="Synthetic history start date.",
    )
    parser.add_argument(
        "--history-end-date",
        default="2025-12-31",
        help="Synthetic history end date.",
    )
    parser.add_argument(
        "--snapshot-date",
        default="2025-12-31",
        help="Customer 360 snapshot date.",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Run generation only and skip validation queries.",
    )
    return parser.parse_args()


def strip_sql_comments(sql: str) -> str:
    cleaned_lines = []
    for line in sql.splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):
            continue
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines)


def split_sql_statements(sql: str) -> list[str]:
    """Split SQL on semicolons outside single quoted strings."""
    sql = strip_sql_comments(sql)
    statements: list[str] = []
    current: list[str] = []
    in_single_quote = False
    i = 0

    while i < len(sql):
        char = sql[i]
        current.append(char)

        if char == "'":
            next_char = sql[i + 1] if i + 1 < len(sql) else ""
            if in_single_quote and next_char == "'":
                current.append(next_char)
                i += 2
                continue
            in_single_quote = not in_single_quote

        if char == ";" and not in_single_quote:
            statement = "".join(current).strip().rstrip(";").strip()
            if statement:
                statements.append(statement)
            current = []

        i += 1

    tail = "".join(current).strip()
    if tail:
        statements.append(tail)

    return statements


def run_cli_json(profile: str, args: list[str], payload: dict | None = None) -> dict:
    cmd = ["databricks", *args, "--profile", profile, "--output", "json"]
    temp_path: Path | None = None

    if payload is not None:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump(payload, handle)
            temp_path = Path(handle.name)
        cmd.extend(["--json", f"@{temp_path}"])

    try:
        completed = subprocess.run(
            cmd,
            cwd=ROOT_DIR,
            check=False,
            capture_output=True,
            text=True,
        )
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)

    if completed.returncode != 0:
        raise RuntimeError(
            "Databricks CLI command failed:\n"
            f"command: {' '.join(cmd)}\n"
            f"stdout: {completed.stdout}\n"
            f"stderr: {completed.stderr}"
        )

    output = completed.stdout.strip()
    return json.loads(output) if output else {}


def print_inline_result(response: dict) -> None:
    result = response.get("result") or {}
    rows = result.get("data_array") or []
    if not rows:
        return

    columns = [
        column.get("name", f"col_{index + 1}")
        for index, column in enumerate(
            response.get("manifest", {}).get("schema", {}).get("columns", [])
        )
    ]
    if columns:
        print("      " + " | ".join(columns))
    for row in rows[:20]:
        print("      " + " | ".join("" if value is None else str(value) for value in row))
    if len(rows) > 20:
        print(f"      ... {len(rows) - 20} more row(s)")


def execute_statement(profile: str, warehouse_id: str, statement: str, label: str) -> dict:
    response = run_cli_json(
        profile,
        ["api", "post", "/api/2.0/sql/statements"],
        {
            "warehouse_id": warehouse_id,
            "statement": statement,
            "wait_timeout": "30s",
            "disposition": "INLINE",
        },
    )

    statement_id = response.get("statement_id")
    status = response.get("status", {})
    state = status.get("state")

    while state in {"PENDING", "RUNNING"}:
        if not statement_id:
            raise RuntimeError(f"{label}: SQL statement did not return a statement_id.")
        time.sleep(3)
        response = run_cli_json(
            profile,
            ["api", "get", f"/api/2.0/sql/statements/{statement_id}"],
        )
        status = response.get("status", {})
        state = status.get("state")

    if state != "SUCCEEDED":
        error = status.get("error", {})
        message = error.get("message") or json.dumps(status, indent=2)
        raise RuntimeError(f"{label}: SQL statement failed with state {state}: {message}")

    print_inline_result(response)
    return response


def execute_sql_file(profile: str, warehouse_id: str, sql_file: Path) -> None:
    statements = split_sql_statements(sql_file.read_text())
    print(f"\n==> {sql_file.name}: {len(statements)} statement(s)")

    for index, statement in enumerate(statements, start=1):
        first_line = re.sub(r"\s+", " ", statement.splitlines()[0]).strip()
        label = f"{sql_file.name} statement {index}/{len(statements)}"
        print(f"    [{index}/{len(statements)}] {first_line[:100]}")
        execute_statement(profile, warehouse_id, statement, label)


def set_generation_config(args: argparse.Namespace) -> None:
    if args.n_customers < 1 or args.n_customers > 1_000_000:
        raise ValueError("--n-customers must be between 1 and 1000000.")

    statement = f"""
DELETE FROM retainflow.monitoring.generation_config;

INSERT INTO retainflow.monitoring.generation_config
SELECT
  'default_dev' AS config_name,
  true AS is_active,
  'reset' AS generation_mode,
  42 AS seed,
  {args.n_customers} AS n_customers,
  to_date('{args.history_start_date}') AS history_start_date,
  to_date('{args.history_end_date}') AS history_end_date,
  to_date('{args.snapshot_date}') AS snapshot_date,
  90 AS prediction_horizon_days,
  1000000 AS max_customer_generation_limit,
  current_timestamp() AS updated_at,
  current_user() AS updated_by;
"""

    print(f"\n==> generation_config: n_customers={args.n_customers}")
    for index, statement_part in enumerate(split_sql_statements(statement), start=1):
        execute_statement(
            args.profile,
            args.warehouse_id,
            statement_part,
            f"generation_config statement {index}",
        )


def main() -> int:
    load_dotenv(ROOT_DIR / ".env")
    args = parse_args()

    if not args.warehouse_id:
        print(
            "Missing SQL warehouse ID. Set DATABRICKS_SQL_WAREHOUSE_ID in .env "
            "or pass --warehouse-id.",
            file=sys.stderr,
        )
        return 2

    print("RetainFlow Phase 1 pipeline")
    print(f"profile      : {args.profile}")
    print(f"warehouse_id : {args.warehouse_id}")
    print(f"n_customers  : {args.n_customers}")

    execute_sql_file(args.profile, args.warehouse_id, SQL_DIR / "00_define_uc_model.sql")
    set_generation_config(args)

    for filename in PIPELINE_FILES[1:]:
        execute_sql_file(args.profile, args.warehouse_id, SQL_DIR / filename)

    if not args.skip_validation:
        for filename in VALIDATION_FILES:
            execute_sql_file(args.profile, args.warehouse_id, SQL_DIR / filename)

    print("\nPipeline completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
