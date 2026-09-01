# RetainFlow - Project Structure

```text
RetainFlow/
├── config/                  YAML configuration files
├── app/                     local RetainFlow agent web console
├── data/
│   ├── docs/                versioned RAG documents for strategy and business knowledge
│   ├── raw/                 generated source CSV files
│   ├── interim/             intermediate local datasets
│   ├── processed/           model-ready exported datasets
│   └── external/            optional external reference data
├── docs/                    architecture and project notes
├── logs/                    local runtime logs
├── notebooks/               step-by-step exploratory notebooks
├── reports/
│   ├── figures/             generated figures
│   └── tables/              generated reporting tables
├── scripts/                 thin command wrappers
├── sql/postgres/            PostgreSQL DDL
├── src/retainflow/          production Python package
│   ├── data/                PostgreSQL loading, CSV ETL, bootstrap, temporal splitting
│   ├── features/            feature engineering and preprocessing contracts
│   ├── generation/          synthetic business data generation
│   ├── models/              CatBoost model class and optimization helpers
│   ├── evaluation/          metrics, confusion matrix, distribution plots
│   ├── explainability/      SHAP explainer, feature importance, agent JSON report
│   ├── tools/               read-only SQL, KPI, retention, SHAP, email, visualization tools
│   ├── agents/              supervisor, SQL, KPI, advisor, email, RAG, visualization agents
│   ├── rag/                 local strategy document loader and TF-IDF retriever
│   ├── prompts/             prompt contracts for future LLM-backed agents
│   ├── pipelines/           runnable workflows: build data, train churn model
│   ├── tracking/            MLflow runtime and UI helpers
│   ├── modeling/            compatibility wrappers for old imports
│   └── utils/               shared helpers
└── tests/                   automated tests
```

The notebooks should show the steps clearly, but reusable logic belongs in `src/retainflow`.
MLflow tracking is configured through `MLFLOW_TRACKING_URI` or `config/churn_model.yml`.

## Active Python Modules

```text
src/retainflow/data/bootstrap.py          class-based PostgreSQL bootstrap workflow
src/retainflow/data/csv_etl.py            CSV generation and PostgreSQL loading helpers
src/retainflow/data/dataset.py            ChurnDatasetLoader and SQLAlchemy DSN helper
src/retainflow/data/splitting.py          TemporalDatasetSplitter and DatasetSplit
src/retainflow/features/engineering.py    churn feature engineering from business dates/signals
src/retainflow/features/preprocessing.py  train-fitted preprocessing and feature contract
src/retainflow/models/catboost_churn.py   ChurnModelTrainer and CatBoost model helpers
src/retainflow/models/optimization.py     first CatBoost search-space helpers
src/retainflow/evaluation/metrics.py      binary metrics and confusion matrix reporter
src/retainflow/evaluation/visualization.py class distribution plotter
src/retainflow/explainability/shap.py     SHAP summaries, plot, and agent payload
src/retainflow/tools/sql_tool.py          read-only SQL execution for agents
src/retainflow/tools/kpi_tool.py          curated business KPI queries
src/retainflow/tools/customer_profile_tool.py customer 360 context retrieval
src/retainflow/tools/visualization_tool.py Plotly Express visualization generation
src/retainflow/tools/rag_tool.py          targeted marketing strategy retrieval
src/retainflow/rag/retriever.py           local TF-IDF retrieval for strategy docs
src/retainflow/agents/supervisor.py       first local supervisor/router agent
src/retainflow/api/app.py                 FastAPI application for the local web console
src/retainflow/pipelines/build_dataset.py data pipeline CLI
src/retainflow/pipelines/train_churn.py   training pipeline CLI and MLflow logging
```

`src/retainflow/modeling/` remains only as a backward-compatible layer while notebooks
and scripts migrate to the new data science architecture.
