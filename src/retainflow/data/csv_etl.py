"""CSV generation and ETL loading for RetainFlow PostgreSQL."""

from __future__ import annotations

import csv
import re
import shutil
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import psycopg

from retainflow.generation import synthetic as generator
from retainflow.logging import get_logger

logger = get_logger(__name__)

DEFAULT_CSV_DIR = generator.ROOT / "data" / "raw" / "retainflow_csv"

LOAD_ORDER = [
    "dim_date",
    "dim_geography",
    "dim_channel",
    "dim_product",
    "dim_agency",
    "dim_agent",
    "dim_customer",
    "fact_policy",
    "fact_policy_event",
    "fact_payment",
    "fact_claim",
    "fact_interaction",
    "fact_customer_service",
    "fact_campaign_contact",
    "fact_quote",
    "fact_retention_action",
    "customer_360_snapshot",
    "churn_label",
    "generation_batch",
]

TABLE_COLUMNS: dict[str, list[str]] = {
    "dim_date": [
        "date_key",
        "calendar_date",
        "calendar_year",
        "calendar_quarter",
        "calendar_month",
        "month_name",
        "day_of_month",
        "day_of_week",
        "week_of_year",
        "is_weekend",
        "is_month_end",
        "is_quarter_end",
        "is_year_end",
    ],
    "dim_geography": [
        "geography_id",
        "country",
        "region",
        "department",
        "city",
        "postal_code",
        "urbanicity",
        "income_index",
        "claim_risk_index",
        "digital_adoption_index",
    ],
    "dim_channel": [
        "channel_id",
        "channel_code",
        "channel_name",
        "channel_family",
        "is_digital",
        "is_inbound",
    ],
    "dim_product": [
        "product_id",
        "product_family",
        "product_name",
        "coverage_tier",
        "base_annual_premium",
        "deductible_amount",
        "risk_level",
        "default_payment_frequency",
    ],
    "dim_agency": [
        "agency_id",
        "agency_code",
        "agency_name",
        "geography_id",
        "agency_type",
        "opened_date",
        "employee_count",
    ],
    "dim_agent": [
        "agent_id",
        "source_agent_id",
        "agent_name",
        "agent_role",
        "channel_id",
        "agency_id",
        "team_name",
        "hire_date",
    ],
    "dim_customer": [
        "customer_id",
        "source_customer_id",
        "first_name",
        "last_name",
        "birth_date",
        "gender",
        "email",
        "phone",
        "geography_id",
        "home_agency_id",
        "acquisition_date",
        "acquisition_channel_id",
        "preferred_channel_id",
        "employment_status",
        "household_size",
        "estimated_income_band",
        "digital_profile",
        "consent_email",
        "consent_sms",
        "consent_phone",
        "customer_segment",
        "risk_affinity_score",
        "price_sensitivity_score",
        "service_sensitivity_score",
        "digital_engagement_score",
        "loyalty_score",
        "claim_propensity_score",
    ],
    "fact_policy": [
        "policy_id",
        "source_policy_id",
        "customer_id",
        "product_id",
        "sales_channel_id",
        "agent_id",
        "agency_id",
        "policy_start_date",
        "policy_end_date",
        "next_renewal_date",
        "policy_status",
        "payment_frequency",
        "annual_premium",
        "premium_discount_pct",
        "premium_increase_pct_last_renewal",
        "cancellation_date",
        "cancellation_reason",
    ],
    "fact_policy_event": [
        "policy_event_id",
        "policy_id",
        "customer_id",
        "product_id",
        "event_date",
        "event_timestamp",
        "event_type",
        "event_reason",
        "previous_policy_status",
        "new_policy_status",
        "previous_annual_premium",
        "new_annual_premium",
        "premium_change_pct",
        "source_system",
    ],
    "fact_payment": [
        "payment_id",
        "policy_id",
        "customer_id",
        "due_date",
        "payment_date",
        "payment_year",
        "payment_amount",
        "payment_status",
        "payment_method",
        "days_late",
        "rejection_reason",
    ],
    "fact_claim": [
        "claim_id",
        "source_claim_id",
        "policy_id",
        "customer_id",
        "product_id",
        "claim_date",
        "reported_date",
        "closed_date",
        "claim_type",
        "claim_status",
        "claim_amount",
        "paid_amount",
        "deductible_amount",
        "handling_days",
        "fraud_suspicion_flag",
        "claim_satisfaction_score",
    ],
    "fact_interaction": [
        "interaction_id",
        "customer_id",
        "policy_id",
        "channel_id",
        "agent_id",
        "interaction_datetime",
        "interaction_year",
        "interaction_type",
        "interaction_reason",
        "direction",
        "duration_seconds",
        "sentiment_score",
        "resolved_flag",
    ],
    "fact_customer_service": [
        "case_id",
        "customer_id",
        "policy_id",
        "interaction_id",
        "opened_datetime",
        "closed_datetime",
        "case_type",
        "priority",
        "case_status",
        "sla_breached_flag",
        "resolution_code",
        "satisfaction_score",
    ],
    "fact_campaign_contact": [
        "campaign_contact_id",
        "campaign_id",
        "customer_id",
        "policy_id",
        "channel_id",
        "campaign_type",
        "campaign_name",
        "contact_datetime",
        "contact_year",
        "opened_flag",
        "clicked_flag",
        "responded_flag",
        "converted_flag",
        "offer_id",
    ],
    "fact_quote": [
        "quote_id",
        "customer_id",
        "product_id",
        "channel_id",
        "agent_id",
        "quote_date",
        "quoted_annual_premium",
        "competitor_price_index",
        "quote_status",
        "converted_policy_id",
    ],
    "fact_retention_action": [
        "retention_action_id",
        "customer_id",
        "policy_id",
        "action_date",
        "action_timestamp",
        "action_type",
        "trigger_reason",
        "offered_value",
        "channel_id",
        "agent_id",
        "accepted_flag",
        "retained_90d_flag",
    ],
    "customer_360_snapshot": [
        "observation_date",
        "customer_id",
        "split_name",
        "tenure_months",
        "active_policy_count",
        "number_of_products",
        "total_annual_premium",
        "total_claims_12m",
        "total_claim_amount_12m",
        "payment_incidents_6m",
        "complaints_6m",
        "interactions_3m",
        "days_since_last_contact",
        "digital_sessions_30d",
        "email_open_rate_6m",
        "premium_increase_pct_max_12m",
        "avg_satisfaction_score_12m",
        "renewal_days_min",
        "customer_value_score",
        "customer_age_years",
        "active_auto_policy_count",
        "active_home_policy_count",
        "active_health_policy_count",
        "active_life_policy_count",
        "cancelled_policy_count_to_date",
        "policy_age_avg_months",
        "late_payment_count_12m",
        "rejected_payment_count_12m",
        "service_case_count_12m",
        "unresolved_case_count_12m",
        "retention_offer_count_12m",
        "retention_acceptance_rate_12m",
        "quote_count_6m",
        "competitor_price_index_avg_6m",
        "campaign_response_rate_6m",
        "main_product_family",
        "highest_coverage_tier",
        "latent_churn_risk_band",
    ],
    "churn_label": [
        "observation_date",
        "customer_id",
        "split_name",
        "prediction_horizon_days",
        "churn_label",
        "churn_date",
        "customer_lifecycle_status",
        "churn_probability",
        "churn_risk_band",
        "label_reason",
    ],
    "generation_batch": [
        "batch_id",
        "run_started_at",
        "run_finished_at",
        "generation_mode",
        "seed",
        "n_customers",
        "history_start_date",
        "history_end_date",
        "status",
        "error_message",
        "created_by",
    ],
}

CONTROLLED_MISSINGNESS = {
    "dim_customer": {"phone": 0.06},
    "fact_policy": {"agent_id": 0.03},
    "fact_payment": {"payment_date": 0.01, "rejection_reason": 0.02},
    "fact_claim": {"closed_date": 0.04, "claim_satisfaction_score": 0.05},
    "fact_interaction": {"agent_id": 0.05},
    "fact_customer_service": {"closed_datetime": 0.03, "satisfaction_score": 0.04},
    "fact_quote": {"agent_id": 0.08, "converted_policy_id": 0.03},
    "customer_360_snapshot": {"avg_satisfaction_score_12m": 0.03, "renewal_days_min": 0.06},
}


def _parse_table_and_columns(sql: str, rows: list[tuple[Any, ...]]) -> tuple[str, list[str]]:
    table_match = re.search(r"INSERT\s+INTO\s+retainflow\.([a-zA-Z0-9_]+)", sql, flags=re.I)
    if not table_match:
        raise ValueError(f"Cannot infer target table from SQL: {sql[:120]}")
    table = table_match.group(1)

    if table == "dim_date":
        return table, TABLE_COLUMNS[table]

    values_match = re.search(rf"retainflow\.{table}\s*\((.*?)\)\s*VALUES", sql, flags=re.I | re.S)
    if not values_match:
        columns = TABLE_COLUMNS[table]
    else:
        columns = [column.strip() for column in values_match.group(1).replace("\n", "").split(",")]

    if rows and len(columns) != len(rows[0]):
        raise ValueError(f"{table}: {len(columns)} columns for {len(rows[0])} values")
    return table, columns


def _format_csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


class CsvDatasetWriter:
    def __init__(self, output_dir: Path, seed: int) -> None:
        self.output_dir = output_dir
        self.rng = np.random.default_rng(seed)
        self.columns_by_table: dict[str, list[str]] = {}
        self.rows_by_table: dict[str, list[tuple[Any, ...]]] = {}

    def reset(self) -> None:
        if self.output_dir.exists():
            shutil.rmtree(self.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write_rows(self, sql: str, rows: list[tuple[Any, ...]]) -> None:
        if not rows:
            return
        table, columns = _parse_table_and_columns(sql, rows)
        self.columns_by_table.setdefault(table, columns)
        self.rows_by_table.setdefault(table, []).extend(rows)

        path = self.output_dir / f"{table}.csv"
        write_header = not path.exists()
        with path.open("a", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            if write_header:
                writer.writerow(columns)
            dirty = CONTROLLED_MISSINGNESS.get(table, {})
            for row in rows:
                row_values = dict(zip(columns, row, strict=True))
                for column, rate in dirty.items():
                    if column in row_values and self.rng.random() < rate:
                        row_values[column] = None
                writer.writerow([_format_csv_value(row_values[column]) for column in columns])

    def write_generation_batch(self, batch_id: str, seed: int, n_customers: int) -> None:
        rows = [
            (
                batch_id,
                datetime.now(UTC),
                datetime.now(UTC),
                "reset",
                seed,
                n_customers,
                generator.HISTORY_START,
                generator.HISTORY_END,
                "SUCCEEDED",
                None,
                "csv_generator",
            )
        ]
        columns = TABLE_COLUMNS["generation_batch"]
        path = self.output_dir / "generation_batch.csv"
        with path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(columns)
            for row in rows:
                writer.writerow([_format_csv_value(value) for value in row])
        self.columns_by_table["generation_batch"] = columns
        self.rows_by_table["generation_batch"] = rows


class _FakeCursor:
    def __init__(self, writer: CsvDatasetWriter) -> None:
        self.writer = writer
        self._result: list[tuple[Any, ...]] = []

    def __enter__(self) -> _FakeCursor:
        return self

    def __exit__(self, *_args: Any) -> None:
        return None

    def execute(self, sql: str, *_args: Any) -> None:
        normalized = " ".join(sql.lower().split())
        if "select agency_id, geography_id from retainflow.dim_agency" in normalized:
            rows = self.writer.rows_by_table.get("dim_agency", [])
            self._result = [(row[0], row[3]) for row in rows]
        elif "select agent_id, agent_role, agency_id from retainflow.dim_agent" in normalized:
            rows = self.writer.rows_by_table.get("dim_agent", [])
            self._result = [(row[0], row[3], row[5]) for row in rows]
        else:
            self._result = []

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self._result


class _FakeConnection:
    def __init__(self, writer: CsvDatasetWriter) -> None:
        self.writer = writer

    def cursor(self) -> _FakeCursor:
        return _FakeCursor(self.writer)


def generate_csv_dataset(output_dir: str | Path, n_customers: int, seed: int) -> Path:
    """Generate one CSV file per target table, with controlled missing values."""
    output_path = Path(output_dir)
    writer = CsvDatasetWriter(output_path, seed)
    writer.reset()

    original_execute_many = generator.execute_many
    generator.execute_many = lambda _conn, sql, rows, batch_size=5000: writer.write_rows(sql, rows)
    try:
        rng = generator.random.Random(seed)
        np.random.seed(seed)
        fake_conn = _FakeConnection(writer)
        refs = generator.seed_reference_data(fake_conn, rng)
        customers = generator.generate_customers(fake_conn, n_customers, rng)
        policies, stats = generator.generate_business_facts(fake_conn, customers, rng)
        generator.generate_snapshots_and_labels(fake_conn, customers, policies, stats, rng)
        writer.write_generation_batch(
            f"BATCH_CSV_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}",
            seed=seed,
            n_customers=n_customers,
        )
        logger.info("Generated CSV dataset in %s; refs=%s", output_path, list(refs))
    finally:
        generator.execute_many = original_execute_many

    return output_path


def load_csv_dataset_to_postgres(input_dir: str | Path, dsn: str, reset: bool = True) -> None:
    """Load generated CSV files into PostgreSQL sequentially by FK dependency order."""
    input_path = Path(input_dir)
    if not input_path.exists():
        raise FileNotFoundError(f"CSV directory does not exist: {input_path}")

    logger.info("Loading CSV dataset from %s to PostgreSQL", input_path)
    with psycopg.connect(dsn, autocommit=False) as conn:
        if reset:
            generator.reset_schema(conn)
        else:
            with conn.cursor() as cur:
                cur.execute(generator.SCHEMA_PATH.read_text(encoding="utf-8"))

        with conn.cursor() as cur:
            for table in LOAD_ORDER:
                path = input_path / f"{table}.csv"
                if not path.exists():
                    logger.info("Skipping missing CSV: %s", path)
                    continue
                columns = TABLE_COLUMNS[table]
                column_list = ", ".join(columns)
                copy_sql = f"COPY retainflow.{table} ({column_list}) FROM STDIN WITH (FORMAT CSV, HEADER TRUE)"
                logger.info("Loading %s", path.name)
                with cur.copy(copy_sql) as copy, path.open("r", encoding="utf-8") as file:
                    while chunk := file.read(1024 * 1024):
                        copy.write(chunk)
        conn.commit()
    logger.info("CSV ETL load complete")


def run_csv_to_postgres(dsn: str, n_customers: int, seed: int, csv_dir: str | Path, reset: bool) -> Path:
    output_path = generate_csv_dataset(csv_dir, n_customers=n_customers, seed=seed)
    load_csv_dataset_to_postgres(output_path, dsn=dsn, reset=reset)
    return output_path
