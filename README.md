# RetainFlow

RetainFlow is a synthetic French insurance data platform for churn prediction, retention prioritization, and future SQL-agent workflows. The first project step now uses local PostgreSQL as the operational source of truth instead of creating the database in Databricks.

## Local Setup

Install Python dependencies with Poetry:

```bash
poetry install
```

Start PostgreSQL:

```bash
docker compose up -d postgres
```

Open the bootstrap notebook and execute the data pipeline step by step:

```text
notebooks/00_postgres_bootstrap_retainflow.ipynb
```

This notebook shows the two explicit data steps:

```python
generate_csv_dataset(CSV_DIR, n_customers=N_CUSTOMERS, seed=SEED)
```

```python
load_csv_dataset_to_postgres(CSV_DIR, dsn=DSN, reset=RESET_DATABASE)
```

Then open the churn training notebook:

```text
notebooks/01_train_churn_catboost.ipynb
```

It shows loading, preprocessing, temporal split, CatBoost training, evaluation, SHAP, MLflow logging, and PostgreSQL prediction saving as separate cells.

MLflow uses the same centralized local store as `BNPL-Credit-Risk`:

```text
tracking_uri: sqlite:////Users/surelmanda/.mlflow/mlflow.db
artifact_uri: file:///Users/surelmanda/.mlflow/artifacts
```

This is configured in `config/churn_model.yml`; the training code uses this central backend directly.

Default connection:

```text
postgresql://retainflow:retainflow@localhost:55432/retainflow
```

## Current Data Foundation

The PostgreSQL schema lives in:

```text
sql/postgres/00_schema.sql
```

The data pipeline is intentionally split in two steps:

```text
1. generate_csv_dataset(...) creates one raw CSV file per table
2. load_csv_dataset_to_postgres(...) loads CSV files into PostgreSQL in FK order
```

Generated CSV files are written by default under:

```text
data/raw/retainflow_csv/
```

The generator creates a realistic French insurance system from 2020 to 2026:

```text
dim_geography              French regions, departments, cities
dim_agency                 local branches, call centers, broker hubs, retention center
dim_channel                web, mobile, agency, call center, broker, email, SMS
dim_agent                  sales, service, claims, retention, hybrid advisors
dim_product                auto, habitation, sante, prevoyance, voyage, animal, accident
dim_customer               demographics, consent, segments, latent behavioral scores
fact_policy                contracts, premiums, renewals, cancellations
fact_payment               installments, late payments, rejections
fact_claim                 claims, paid amounts, handling delays, satisfaction
fact_interaction           customer touchpoints by channel and reason
fact_customer_service      complaints, billing issues, claim support cases
fact_campaign_contact      marketing and retention contacts
fact_quote                 quotes and competitor pressure
fact_retention_action      historical save actions and outcomes
customer_360_snapshot      ML-ready features from customer, policy, payment, claim, service, campaign, quote, and retention relations
churn_label                supervised labels for churn modeling
```

`customer_360_snapshot` keeps relational signals that a churn model can learn from, including
customer age, product mix, active policy counts by family, cancelled policies to date, average
policy age, late and rejected payments, service cases, unresolved cases, retention offer history,
quote pressure, competitor price index, and campaign response behavior.

The ML splits are temporal:

```text
train       2021-12-31, 2022-12-31, 2023-12-31
validation 2024-12-31
test        2025-12-31
backtest    2026-06-30
```

## Project Flow

```text
config            YAML configuration
data              raw/interim/processed/external local data zones
sql/postgres      PostgreSQL schema
src/retainflow     production Python package organized by data science responsibility
scripts           thin command wrappers
notebooks         step-by-step notebooks
models            exported model artifacts
reports           generated figures and tables
legacy_databricks archived Databricks SQL/assets from the previous approach
churn_model        first churn model notebook, MLflow tracking, batch churn predictions
retention_engine   next step: retention prioritization and recommended actions
agents             future step: agentic workflows over the governed data platform
monitoring         future step: pipeline, data quality, model, and business monitoring
```

## Documentation

```text
docs/01_architecture_data_model.md     initial data architecture design
docs/02_etat_de_l_art_retainflow.md    current project state of the art and roadmap
```

The churn model configuration lives in:

```text
config/churn_model.yml
```

The churn model follows a real data science project structure, not notebook-only logic:

```text
src/retainflow/config.py                 typed YAML config loading
src/retainflow/logging.py                project logger writing to logs/retainflow.log
src/retainflow/data/bootstrap.py         class-based PostgreSQL bootstrap workflow
src/retainflow/data/csv_etl.py           CSV generation and PostgreSQL ETL
src/retainflow/data/dataset.py           ChurnDatasetLoader for PostgreSQL loading
src/retainflow/data/splitting.py         TemporalDatasetSplitter for train / validation / test / backtest split
src/retainflow/features/engineering.py   business feature engineering
src/retainflow/features/preprocessing.py train-fitted preprocessing and feature contract
src/retainflow/models/catboost_churn.py  ChurnModelTrainer for CatBoost
src/retainflow/models/optimization.py    CatBoost search-space helpers
src/retainflow/evaluation/metrics.py     BinaryClassifierEvaluator and ConfusionMatrixReporter
src/retainflow/evaluation/visualization.py ClassDistributionPlotter
src/retainflow/explainability/shap.py    SHAP values, plots, and agent JSON
src/retainflow/pipelines/train_churn.py  MLflow training pipeline and prediction saving
src/retainflow/generation/synthetic.py   synthetic business data generation
notebooks/01_train_churn_catboost.ipynb first local ML notebook
legacy_databricks/                    old Spark/CatBoost training path archived
```

`src/retainflow/modeling/` is kept only as a compatibility layer for old imports.

Logs are written to:

```text
logs/retainflow.log
```

SHAP explainability artifacts are generated under:

```text
reports/figures/class_distribution_by_split.png
reports/figures/confusion_matrix_by_split.png
reports/tables/confusion_matrix_by_split.csv
reports/tables/shap_summary.csv
reports/tables/shap_agent_report.json
reports/figures/shap_feature_importance.png
```

## Optional CLI

The notebooks are the recommended path while the project is being built and explained. Thin CLI wrappers exist only for repeatable automation:

```bash
poetry run retainflow-build-data --reset --n-customers 10000
poetry run retainflow-train-churn --config config/churn_model.yml
```

## Quick SQL Checks

```sql
SELECT split_name, count(*) AS rows, avg(churn_label) AS churn_rate
FROM retainflow.churn_label
GROUP BY split_name
ORDER BY split_name;

SELECT a.agency_name, g.region, count(*) AS customers
FROM retainflow.dim_customer c
JOIN retainflow.dim_agency a ON a.agency_id = c.home_agency_id
JOIN retainflow.dim_geography g ON g.geography_id = a.geography_id
GROUP BY a.agency_name, g.region
ORDER BY customers DESC
LIMIT 10;
```

## Legacy Databricks

Databricks table creation is no longer part of the active flow. The previous Databricks assets are archived under `legacy_databricks/` for reference only.
