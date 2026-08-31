-- RetainFlow - architecture validation dashboard queries
-- Run whenever you want to confirm what was really created in Databricks.

WITH expected_schemas AS (
  SELECT *
  FROM VALUES
    ('raw'),
    ('bronze'),
    ('silver'),
    ('gold'),
    ('ml'),
    ('monitoring')
  AS expected(schema_name)
),
actual_schemas AS (
  SELECT schema_name
  FROM retainflow.information_schema.schemata
  WHERE catalog_name = 'retainflow'
)
SELECT
  e.schema_name,
  CASE WHEN a.schema_name IS NULL THEN 'MISSING' ELSE 'OK' END AS status
FROM expected_schemas e
LEFT JOIN actual_schemas a
  ON e.schema_name = a.schema_name
ORDER BY e.schema_name;

WITH expected_tables AS (
  SELECT *
  FROM VALUES
    ('silver', 'dim_date'),
    ('silver', 'dim_geography'),
    ('silver', 'dim_channel'),
    ('silver', 'dim_agent'),
    ('silver', 'dim_product'),
    ('silver', 'dim_customer'),
    ('silver', 'fact_policy'),
    ('silver', 'fact_policy_events'),
    ('silver', 'fact_claims'),
    ('silver', 'fact_payments'),
    ('silver', 'fact_interactions'),
    ('silver', 'fact_customer_service'),
    ('silver', 'fact_campaign_contact'),
    ('silver', 'fact_quotes'),
    ('silver', 'fact_retention_actions'),
    ('gold', 'customer_360_snapshot'),
    ('gold', 'retention_priority_queue'),
    ('ml', 'churn_feature_snapshot'),
    ('ml', 'churn_labels'),
    ('ml', 'churn_predictions'),
    ('monitoring', 'generation_config'),
    ('monitoring', 'generation_batches'),
    ('monitoring', 'data_quality_results'),
    ('monitoring', 'logical_relationships')
  AS expected(table_schema, table_name)
),
actual_tables AS (
  SELECT table_schema, table_name
  FROM retainflow.information_schema.tables
  WHERE table_catalog = 'retainflow'
)
SELECT
  e.table_schema,
  e.table_name,
  CASE WHEN a.table_name IS NULL THEN 'MISSING' ELSE 'OK' END AS status
FROM expected_tables e
LEFT JOIN actual_tables a
  ON e.table_schema = a.table_schema
 AND e.table_name = a.table_name
ORDER BY e.table_schema, e.table_name;

SELECT *
FROM retainflow.monitoring.generation_config
ORDER BY is_active DESC, updated_at DESC;

SELECT 'silver.dim_date' AS table_name, count(*) AS row_count FROM retainflow.silver.dim_date
UNION ALL SELECT 'silver.dim_geography', count(*) FROM retainflow.silver.dim_geography
UNION ALL SELECT 'silver.dim_channel', count(*) FROM retainflow.silver.dim_channel
UNION ALL SELECT 'silver.dim_agent', count(*) FROM retainflow.silver.dim_agent
UNION ALL SELECT 'silver.dim_product', count(*) FROM retainflow.silver.dim_product
UNION ALL SELECT 'silver.dim_customer', count(*) FROM retainflow.silver.dim_customer
UNION ALL SELECT 'silver.fact_policy', count(*) FROM retainflow.silver.fact_policy
UNION ALL SELECT 'silver.fact_policy_events', count(*) FROM retainflow.silver.fact_policy_events
UNION ALL SELECT 'silver.fact_claims', count(*) FROM retainflow.silver.fact_claims
UNION ALL SELECT 'silver.fact_payments', count(*) FROM retainflow.silver.fact_payments
UNION ALL SELECT 'silver.fact_interactions', count(*) FROM retainflow.silver.fact_interactions
UNION ALL SELECT 'silver.fact_customer_service', count(*) FROM retainflow.silver.fact_customer_service
UNION ALL SELECT 'silver.fact_campaign_contact', count(*) FROM retainflow.silver.fact_campaign_contact
UNION ALL SELECT 'silver.fact_quotes', count(*) FROM retainflow.silver.fact_quotes
UNION ALL SELECT 'silver.fact_retention_actions', count(*) FROM retainflow.silver.fact_retention_actions
UNION ALL SELECT 'gold.customer_360_snapshot', count(*) FROM retainflow.gold.customer_360_snapshot
UNION ALL SELECT 'gold.retention_priority_queue', count(*) FROM retainflow.gold.retention_priority_queue
UNION ALL SELECT 'ml.churn_feature_snapshot', count(*) FROM retainflow.ml.churn_feature_snapshot
UNION ALL SELECT 'ml.churn_labels', count(*) FROM retainflow.ml.churn_labels
UNION ALL SELECT 'ml.churn_predictions', count(*) FROM retainflow.ml.churn_predictions
UNION ALL SELECT 'monitoring.generation_config', count(*) FROM retainflow.monitoring.generation_config
UNION ALL SELECT 'monitoring.generation_batches', count(*) FROM retainflow.monitoring.generation_batches
UNION ALL SELECT 'monitoring.data_quality_results', count(*) FROM retainflow.monitoring.data_quality_results
UNION ALL SELECT 'monitoring.logical_relationships', count(*) FROM retainflow.monitoring.logical_relationships
ORDER BY table_name;

SELECT *
FROM retainflow.monitoring.generation_batches
ORDER BY run_finished_at DESC
LIMIT 10;
