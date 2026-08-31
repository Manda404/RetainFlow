-- Databricks notebook source
-- RetainFlow - Monitoring Dashboard
-- Notebook SQL pour surveiller pipeline, data quality, ML scoring et retention.

-- COMMAND ----------

USE CATALOG retainflow;

-- COMMAND ----------

SELECT
  current_timestamp() AS checked_at,
  current_catalog() AS catalog_name,
  current_schema() AS schema_name;

-- COMMAND ----------

SELECT
  status,
  count(*) AS batches,
  max(run_finished_at) AS last_finished_at
FROM retainflow.monitoring.generation_batches
GROUP BY status
ORDER BY last_finished_at DESC;

-- COMMAND ----------

SELECT
  batch_id,
  generation_mode,
  seed,
  n_customers,
  history_start_date,
  history_end_date,
  status,
  run_started_at,
  run_finished_at,
  round((unix_timestamp(run_finished_at) - unix_timestamp(run_started_at)) / 60, 2) AS duration_minutes,
  created_by
FROM retainflow.monitoring.generation_batches
ORDER BY run_finished_at DESC
LIMIT 30;

-- COMMAND ----------

SELECT
  check_status,
  count(*) AS checks,
  sum(failed_row_count) AS failed_rows
FROM retainflow.monitoring.data_quality_results
GROUP BY check_status
ORDER BY check_status;

-- COMMAND ----------

SELECT
  schema_name,
  table_name,
  check_type,
  check_status,
  count(*) AS checks,
  sum(failed_row_count) AS failed_rows
FROM retainflow.monitoring.data_quality_results
GROUP BY schema_name, table_name, check_type, check_status
ORDER BY schema_name, table_name, check_type, check_status;

-- COMMAND ----------

SELECT
  schema_name,
  table_name,
  check_name,
  check_type,
  check_status,
  observed_value,
  expected_value,
  failed_row_count,
  check_message,
  checked_at
FROM retainflow.monitoring.data_quality_results
WHERE check_status <> 'PASS'
ORDER BY failed_row_count DESC, schema_name, table_name, check_name;

-- COMMAND ----------

SELECT 'silver.dim_customer' AS table_name, count(*) AS row_count FROM retainflow.silver.dim_customer
UNION ALL SELECT 'silver.fact_policy', count(*) FROM retainflow.silver.fact_policy
UNION ALL SELECT 'silver.fact_policy_events', count(*) FROM retainflow.silver.fact_policy_events
UNION ALL SELECT 'silver.fact_payments', count(*) FROM retainflow.silver.fact_payments
UNION ALL SELECT 'silver.fact_claims', count(*) FROM retainflow.silver.fact_claims
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
ORDER BY table_name;

-- COMMAND ----------

SELECT
  scoring_run_id,
  model_name,
  count(*) AS scored_customers,
  round(avg(churn_probability), 4) AS avg_churn_probability,
  round(min(churn_probability), 4) AS min_churn_probability,
  round(max(churn_probability), 4) AS max_churn_probability,
  min(scored_at) AS first_scored_at,
  max(scored_at) AS last_scored_at
FROM retainflow.ml.churn_predictions
GROUP BY scoring_run_id, model_name
ORDER BY last_scored_at DESC;

-- COMMAND ----------

SELECT
  churn_risk_band,
  count(*) AS scored_customers,
  round(avg(churn_probability), 4) AS avg_churn_probability
FROM retainflow.ml.churn_predictions
GROUP BY churn_risk_band
ORDER BY
  CASE churn_risk_band
    WHEN 'VERY_HIGH' THEN 1
    WHEN 'HIGH' THEN 2
    WHEN 'MEDIUM' THEN 3
    ELSE 4
  END;

-- COMMAND ----------

SELECT
  priority_tier,
  count(*) AS recommended_customers,
  round(avg(priority_score), 2) AS avg_priority_score,
  round(avg(churn_probability), 4) AS avg_churn_probability,
  round(sum(estimated_offer_value), 2) AS estimated_offer_budget
FROM retainflow.gold.retention_priority_queue
GROUP BY priority_tier
ORDER BY priority_tier;

-- COMMAND ----------

SELECT
  recommended_action_type,
  priority_tier,
  count(*) AS recommended_customers,
  round(sum(estimated_offer_value), 2) AS estimated_offer_budget
FROM retainflow.gold.retention_priority_queue
GROUP BY recommended_action_type, priority_tier
ORDER BY recommended_action_type, priority_tier;

-- COMMAND ----------

WITH coverage AS (
  SELECT
    (SELECT count(*) FROM retainflow.silver.dim_customer) AS customers,
    (SELECT count(*) FROM retainflow.gold.customer_360_snapshot) AS customer_360_rows,
    (SELECT count(*) FROM retainflow.ml.churn_feature_snapshot) AS feature_rows,
    (SELECT count(*) FROM retainflow.ml.churn_labels) AS label_rows,
    (SELECT count(*) FROM retainflow.ml.churn_predictions) AS prediction_rows,
    (SELECT count(*) FROM retainflow.gold.retention_priority_queue) AS recommendation_rows
)
SELECT 'customers' AS metric, customers AS value FROM coverage
UNION ALL SELECT 'customer_360_rows', customer_360_rows FROM coverage
UNION ALL SELECT 'feature_rows', feature_rows FROM coverage
UNION ALL SELECT 'label_rows', label_rows FROM coverage
UNION ALL SELECT 'prediction_rows', prediction_rows FROM coverage
UNION ALL SELECT 'recommendation_rows', recommendation_rows FROM coverage;
