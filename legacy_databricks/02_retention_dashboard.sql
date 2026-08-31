-- Databricks notebook source
-- RetainFlow - Retention Dashboard
-- Notebook SQL pour piloter les clients a risque et les actions de retention.

-- COMMAND ----------

USE CATALOG retainflow;

-- COMMAND ----------

SELECT
  'churn_predictions' AS asset,
  count(*) AS rows
FROM retainflow.ml.churn_predictions
UNION ALL
SELECT
  'retention_priority_queue' AS asset,
  count(*) AS rows
FROM retainflow.gold.retention_priority_queue;

-- COMMAND ----------

SELECT
  priority_tier,
  count(*) AS customers,
  round(avg(churn_probability), 4) AS avg_churn_probability,
  round(avg(priority_score), 2) AS avg_priority_score,
  round(sum(estimated_offer_value), 2) AS estimated_offer_budget
FROM retainflow.gold.retention_priority_queue
GROUP BY priority_tier
ORDER BY priority_tier;

-- COMMAND ----------

SELECT
  churn_risk_band,
  priority_tier,
  count(*) AS customers,
  round(avg(churn_probability), 4) AS avg_churn_probability,
  round(avg(customer_value_score), 4) AS avg_customer_value_score
FROM retainflow.gold.retention_priority_queue
GROUP BY churn_risk_band, priority_tier
ORDER BY
  CASE churn_risk_band
    WHEN 'VERY_HIGH' THEN 1
    WHEN 'HIGH' THEN 2
    WHEN 'MEDIUM' THEN 3
    ELSE 4
  END,
  priority_tier;

-- COMMAND ----------

SELECT
  recommended_action_type,
  count(*) AS customers,
  round(avg(churn_probability), 4) AS avg_churn_probability,
  round(avg(priority_score), 2) AS avg_priority_score,
  round(sum(estimated_offer_value), 2) AS estimated_offer_budget
FROM retainflow.gold.retention_priority_queue
GROUP BY recommended_action_type
ORDER BY customers DESC;

-- COMMAND ----------

SELECT
  recommended_channel_name,
  count(*) AS customers,
  round(avg(priority_score), 2) AS avg_priority_score,
  round(sum(estimated_offer_value), 2) AS estimated_offer_budget
FROM retainflow.gold.retention_priority_queue
GROUP BY recommended_channel_name
ORDER BY customers DESC;

-- COMMAND ----------

SELECT
  action_reason,
  count(*) AS customers,
  round(avg(churn_probability), 4) AS avg_churn_probability,
  round(avg(priority_score), 2) AS avg_priority_score
FROM retainflow.gold.retention_priority_queue
GROUP BY action_reason
ORDER BY customers DESC;

-- COMMAND ----------

SELECT
  q.priority_tier,
  c.customer_segment,
  c.estimated_income_band,
  count(*) AS customers,
  round(avg(q.churn_probability), 4) AS avg_churn_probability,
  round(avg(q.priority_score), 2) AS avg_priority_score,
  round(sum(q.estimated_offer_value), 2) AS estimated_offer_budget
FROM retainflow.gold.retention_priority_queue q
JOIN retainflow.silver.dim_customer c
  ON q.customer_id = c.customer_id
GROUP BY q.priority_tier, c.customer_segment, c.estimated_income_band
ORDER BY q.priority_tier, customers DESC;

-- COMMAND ----------

SELECT
  CASE
    WHEN g.renewal_days_min BETWEEN 0 AND 30 THEN '0-30 days'
    WHEN g.renewal_days_min BETWEEN 31 AND 60 THEN '31-60 days'
    WHEN g.renewal_days_min BETWEEN 61 AND 90 THEN '61-90 days'
    WHEN g.renewal_days_min BETWEEN 91 AND 180 THEN '91-180 days'
    ELSE '180+ days'
  END AS renewal_window,
  count(*) AS customers,
  round(avg(q.churn_probability), 4) AS avg_churn_probability,
  round(avg(q.priority_score), 2) AS avg_priority_score
FROM retainflow.gold.retention_priority_queue q
JOIN retainflow.gold.customer_360_snapshot g
  ON q.customer_id = g.customer_id
 AND q.observation_date = g.observation_date
GROUP BY
  CASE
    WHEN g.renewal_days_min BETWEEN 0 AND 30 THEN '0-30 days'
    WHEN g.renewal_days_min BETWEEN 31 AND 60 THEN '31-60 days'
    WHEN g.renewal_days_min BETWEEN 61 AND 90 THEN '61-90 days'
    WHEN g.renewal_days_min BETWEEN 91 AND 180 THEN '91-180 days'
    ELSE '180+ days'
  END
ORDER BY
  CASE renewal_window
    WHEN '0-30 days' THEN 1
    WHEN '31-60 days' THEN 2
    WHEN '61-90 days' THEN 3
    WHEN '91-180 days' THEN 4
    ELSE 5
  END;

-- COMMAND ----------

SELECT
  q.priority_tier,
  q.customer_id,
  c.first_name,
  c.last_name,
  c.customer_segment,
  c.estimated_income_band,
  q.churn_probability,
  q.priority_score,
  q.recommended_action_type,
  q.action_reason,
  q.recommended_channel_name,
  q.estimated_offer_value,
  q.total_annual_premium,
  q.renewal_days_min,
  q.model_name,
  q.scoring_run_id
FROM retainflow.gold.retention_priority_queue q
JOIN retainflow.silver.dim_customer c
  ON q.customer_id = c.customer_id
ORDER BY q.priority_score DESC, q.churn_probability DESC
LIMIT 100;

-- COMMAND ----------

SELECT
  q.customer_id,
  q.priority_tier,
  q.churn_probability,
  q.priority_score,
  q.recommended_action_type,
  q.action_reason,
  g.active_policy_count,
  g.number_of_products,
  g.total_annual_premium,
  g.total_claims_12m,
  g.payment_incidents_6m,
  g.complaints_6m,
  g.days_since_last_contact,
  g.email_open_rate_6m,
  g.avg_satisfaction_score_12m,
  g.renewal_days_min
FROM retainflow.gold.retention_priority_queue q
JOIN retainflow.gold.customer_360_snapshot g
  ON q.customer_id = g.customer_id
 AND q.observation_date = g.observation_date
WHERE q.priority_tier IN ('P1', 'P2')
ORDER BY q.priority_score DESC
LIMIT 100;

-- COMMAND ----------

WITH checks AS (
  SELECT
    count(*) AS recommendation_count,
    count(DISTINCT recommendation_id) AS distinct_recommendations,
    count(DISTINCT customer_id) AS distinct_customers,
    count(CASE WHEN recommended_channel_id IS NULL THEN 1 END) AS missing_channel_count,
    count(CASE WHEN priority_score IS NULL THEN 1 END) AS missing_priority_score_count,
    count(CASE WHEN estimated_offer_value < 0 THEN 1 END) AS negative_offer_value_count
  FROM retainflow.gold.retention_priority_queue
)
SELECT 'recommendation_count' AS metric, CAST(recommendation_count AS STRING) AS value FROM checks
UNION ALL SELECT 'distinct_recommendations', CAST(distinct_recommendations AS STRING) FROM checks
UNION ALL SELECT 'distinct_customers', CAST(distinct_customers AS STRING) FROM checks
UNION ALL SELECT 'duplicate_recommendation_count', CAST(recommendation_count - distinct_recommendations AS STRING) FROM checks
UNION ALL SELECT 'duplicate_customer_count', CAST(recommendation_count - distinct_customers AS STRING) FROM checks
UNION ALL SELECT 'missing_channel_count', CAST(missing_channel_count AS STRING) FROM checks
UNION ALL SELECT 'missing_priority_score_count', CAST(missing_priority_score_count AS STRING) FROM checks
UNION ALL SELECT 'negative_offer_value_count', CAST(negative_offer_value_count AS STRING) FROM checks
ORDER BY metric;

-- COMMAND ----------

SELECT
  scoring_run_id,
  model_name,
  min(scored_at) AS first_score_at,
  max(scored_at) AS last_score_at,
  count(*) AS scored_customers,
  round(avg(churn_probability), 4) AS avg_churn_probability
FROM retainflow.ml.churn_predictions
GROUP BY scoring_run_id, model_name
ORDER BY last_score_at DESC;
