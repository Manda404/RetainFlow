# Databricks notebook source
# MAGIC %md
# MAGIC # RetainFlow - Phase 1 Data Pipeline
# MAGIC
# MAGIC Databricks-native runner for the Phase 1 SQL pipeline.
# MAGIC This notebook executes the SQL files with `spark.sql` so it can run inside a Databricks Job.

# COMMAND ----------

# MAGIC %pip install pyyaml

# COMMAND ----------

from pathlib import Path
import yaml

# COMMAND ----------

PROJECT_ROOT = Path("/Workspace/Users/s239150.eps@gmail.com/RetainFlow")
LOCAL_PROJECT_ROOT = Path.cwd()

SQL_DIR = PROJECT_ROOT / "data_engineering"
if not SQL_DIR.exists():
    SQL_DIR = LOCAL_PROJECT_ROOT / "data_engineering"

CONFIG_PATH = PROJECT_ROOT / "config" / "data_pipeline.yml"
if not CONFIG_PATH.exists():
    CONFIG_PATH = LOCAL_PROJECT_ROOT / "config" / "data_pipeline.yml"

with CONFIG_PATH.open(encoding="utf-8") as config_file:
    pipeline_config = yaml.safe_load(config_file) or {}

N_CUSTOMERS = int(pipeline_config["n_customers"])
HISTORY_START_DATE = str(pipeline_config["history_start_date"])
HISTORY_END_DATE = str(pipeline_config["history_end_date"])
SNAPSHOT_DATE = str(pipeline_config["snapshot_date"])
PREDICTION_HORIZON_DAYS = int(pipeline_config["prediction_horizon_days"])

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

# COMMAND ----------

def strip_sql_comments(sql: str) -> str:
    cleaned_lines = []
    for line in sql.splitlines():
        if line.strip().startswith("--"):
            continue
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines)


def split_sql_statements(sql: str) -> list[str]:
    sql = strip_sql_comments(sql)
    statements = []
    current = []
    in_single_quote = False
    index = 0

    while index < len(sql):
        char = sql[index]
        current.append(char)

        if char == "'":
            next_char = sql[index + 1] if index + 1 < len(sql) else ""
            if in_single_quote and next_char == "'":
                current.append(next_char)
                index += 2
                continue
            in_single_quote = not in_single_quote

        if char == ";" and not in_single_quote:
            statement = "".join(current).strip().rstrip(";").strip()
            if statement:
                statements.append(statement)
            current = []

        index += 1

    trailing = "".join(current).strip()
    if trailing:
        statements.append(trailing)

    return statements


def execute_sql_file(filename: str) -> None:
    path = SQL_DIR / filename
    if not path.exists():
        raise FileNotFoundError(path)

    statements = split_sql_statements(path.read_text(encoding="utf-8"))
    print(f"\n==> {filename}: {len(statements)} statement(s)")

    for index, statement in enumerate(statements, start=1):
        print(f"   [{index}/{len(statements)}] {statement.splitlines()[0][:120]}")
        spark.sql(statement)


def set_generation_config() -> None:
    print(f"\n==> generation_config: n_customers={N_CUSTOMERS}")
    spark.sql(
        f"""
        CREATE OR REPLACE TEMP VIEW retainflow_generation_config AS
        SELECT
          'default' AS config_id,
          true AS is_active,
          'SYNTHETIC_SQL' AS generation_mode,
          42 AS seed,
          {N_CUSTOMERS} AS n_customers,
          to_date('{HISTORY_START_DATE}') AS history_start_date,
          to_date('{HISTORY_END_DATE}') AS history_end_date,
          to_date('{SNAPSHOT_DATE}') AS snapshot_date,
          {PREDICTION_HORIZON_DAYS} AS prediction_horizon_days,
          1000000 AS max_customer_generation_limit,
          current_timestamp() AS updated_at,
          current_user() AS updated_by
        """
    )
    spark.sql("DELETE FROM retainflow.monitoring.generation_config WHERE config_id = 'default'")
    spark.sql(
        """
        INSERT INTO retainflow.monitoring.generation_config
        SELECT * FROM retainflow_generation_config
        """
    )

# COMMAND ----------

execute_sql_file("00_define_uc_model.sql")
set_generation_config()

for pipeline_file in PIPELINE_FILES[1:]:
    execute_sql_file(pipeline_file)

for validation_file in VALIDATION_FILES:
    execute_sql_file(validation_file)

print("\nPipeline completed successfully.")
