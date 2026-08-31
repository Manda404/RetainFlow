-- Databricks notebook source
-- RetainFlow - SQL Exploration
-- Notebook SQL pour tester des commandes et visualiser les tables creees.

-- COMMAND ----------

USE CATALOG retainflow;

-- COMMAND ----------

SHOW SCHEMAS IN retainflow;

-- COMMAND ----------

SHOW TABLES IN retainflow.silver;

-- COMMAND ----------

SHOW TABLES IN retainflow.gold;

-- COMMAND ----------

SHOW TABLES IN retainflow.monitoring;

-- COMMAND ----------

SELECT *
FROM retainflow.monitoring.generation_config
WHERE is_active = true;

-- COMMAND ----------

SELECT 'silver.dim_date' AS table_name, count(*) AS row_count FROM retainflow.silver.dim_date
UNION ALL SELECT 'silver.dim_geography', count(*) FROM retainflow.silver.dim_geography
UNION ALL SELECT 'silver.dim_channel', count(*) FROM retainflow.silver.dim_channel
UNION ALL SELECT 'silver.dim_agent', count(*) FROM retainflow.silver.dim_agent
UNION ALL SELECT 'silver.dim_product', count(*) FROM retainflow.silver.dim_product
UNION ALL SELECT 'silver.dim_customer', count(*) FROM retainflow.silver.dim_customer
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
UNION ALL SELECT 'ml.churn_feature_snapshot', count(*) FROM retainflow.ml.churn_feature_snapshot
UNION ALL SELECT 'ml.churn_labels', count(*) FROM retainflow.ml.churn_labels
UNION ALL SELECT 'monitoring.logical_relationships', count(*) FROM retainflow.monitoring.logical_relationships
UNION ALL SELECT 'monitoring.generation_batches', count(*) FROM retainflow.monitoring.generation_batches
UNION ALL SELECT 'monitoring.data_quality_results', count(*) FROM retainflow.monitoring.data_quality_results
ORDER BY table_name;

-- COMMAND ----------

SELECT *
FROM retainflow.silver.dim_product
ORDER BY product_family, coverage_tier;

-- COMMAND ----------

SELECT *
FROM retainflow.silver.dim_channel
ORDER BY channel_family, channel_code;

-- COMMAND ----------

SELECT *
FROM retainflow.silver.dim_geography
ORDER BY region, city;

-- COMMAND ----------

SELECT *
FROM retainflow.silver.dim_agent
ORDER BY geography_id, agent_role, agent_id
LIMIT 50;

-- COMMAND ----------

SELECT *
FROM retainflow.silver.dim_customer
LIMIT 100;

-- COMMAND ----------

SELECT
  customer_segment,
  count(*) AS customers,
  round(avg(price_sensitivity_score), 3) AS avg_price_sensitivity,
  round(avg(digital_engagement_score), 3) AS avg_digital_engagement,
  round(avg(loyalty_score), 3) AS avg_loyalty
FROM retainflow.silver.dim_customer
GROUP BY customer_segment
ORDER BY customers DESC;

-- COMMAND ----------

SELECT
  estimated_income_band,
  digital_profile,
  count(*) AS customers
FROM retainflow.silver.dim_customer
GROUP BY estimated_income_band, digital_profile
ORDER BY estimated_income_band, digital_profile;

-- COMMAND ----------

SELECT *
FROM retainflow.silver.fact_policy
LIMIT 100;

-- COMMAND ----------

SELECT
  policy_status,
  count(*) AS policies,
  round(avg(annual_premium), 2) AS avg_annual_premium,
  round(avg(premium_increase_pct_last_renewal), 4) AS avg_premium_increase_pct
FROM retainflow.silver.fact_policy
GROUP BY policy_status
ORDER BY policies DESC;

-- COMMAND ----------

SELECT
  pr.product_family,
  pr.coverage_tier,
  count(*) AS policies,
  round(avg(p.annual_premium), 2) AS avg_annual_premium
FROM retainflow.silver.fact_policy p
JOIN retainflow.silver.dim_product pr
  ON p.product_id = pr.product_id
GROUP BY pr.product_family, pr.coverage_tier
ORDER BY pr.product_family, pr.coverage_tier;

-- COMMAND ----------

SELECT *
FROM retainflow.silver.fact_policy_events
ORDER BY event_timestamp DESC
LIMIT 100;

-- COMMAND ----------

SELECT
  event_type,
  count(*) AS events,
  min(event_date) AS first_event_date,
  max(event_date) AS last_event_date
FROM retainflow.silver.fact_policy_events
GROUP BY event_type
ORDER BY events DESC;

-- COMMAND ----------

SELECT *
FROM retainflow.silver.fact_payments
LIMIT 100;

-- COMMAND ----------

SELECT
  payment_status,
  count(*) AS payments,
  round(avg(payment_amount), 2) AS avg_payment_amount,
  round(avg(coalesce(days_late, 0)), 2) AS avg_days_late
FROM retainflow.silver.fact_payments
GROUP BY payment_status
ORDER BY payments DESC;

-- COMMAND ----------

SELECT *
FROM retainflow.silver.fact_claims
ORDER BY claim_date DESC
LIMIT 100;

-- COMMAND ----------

SELECT
  claim_status,
  count(*) AS claims,
  round(avg(claim_amount), 2) AS avg_claim_amount,
  round(avg(paid_amount), 2) AS avg_paid_amount,
  round(avg(handling_days), 2) AS avg_handling_days,
  round(avg(claim_satisfaction_score), 3) AS avg_satisfaction
FROM retainflow.silver.fact_claims
GROUP BY claim_status
ORDER BY claims DESC;

-- COMMAND ----------

SELECT
  pr.product_family,
  count(*) AS claims,
  round(avg(clm.claim_amount), 2) AS avg_claim_amount,
  round(avg(clm.claim_satisfaction_score), 3) AS avg_satisfaction
FROM retainflow.silver.fact_claims clm
JOIN retainflow.silver.dim_product pr
  ON clm.product_id = pr.product_id
GROUP BY pr.product_family
ORDER BY claims DESC;

-- COMMAND ----------

SELECT *
FROM retainflow.silver.fact_interactions
ORDER BY interaction_datetime DESC
LIMIT 100;

-- COMMAND ----------

SELECT
  channel_id,
  interaction_type,
  count(*) AS interactions,
  round(avg(sentiment_score), 4) AS avg_sentiment
FROM retainflow.silver.fact_interactions
GROUP BY channel_id, interaction_type
ORDER BY interactions DESC;

-- COMMAND ----------

SELECT
  interaction_reason,
  direction,
  count(*) AS interactions,
  round(avg(duration_seconds), 2) AS avg_duration_seconds,
  round(avg(sentiment_score), 4) AS avg_sentiment
FROM retainflow.silver.fact_interactions
GROUP BY interaction_reason, direction
ORDER BY interactions DESC;

-- COMMAND ----------

SELECT *
FROM retainflow.silver.fact_customer_service
ORDER BY opened_datetime DESC
LIMIT 100;

-- COMMAND ----------

SELECT
  case_type,
  priority,
  case_status,
  count(*) AS service_cases,
  round(avg(satisfaction_score), 3) AS avg_satisfaction
FROM retainflow.silver.fact_customer_service
GROUP BY case_type, priority, case_status
ORDER BY service_cases DESC;

-- COMMAND ----------

SELECT *
FROM retainflow.silver.fact_campaign_contact
ORDER BY contact_datetime DESC
LIMIT 100;

-- COMMAND ----------

SELECT
  campaign_type,
  channel_id,
  count(*) AS contacts,
  round(avg(CASE WHEN opened_flag THEN 1.0 ELSE 0.0 END), 4) AS open_rate,
  round(avg(CASE WHEN clicked_flag THEN 1.0 ELSE 0.0 END), 4) AS click_rate,
  round(avg(CASE WHEN converted_flag THEN 1.0 ELSE 0.0 END), 4) AS conversion_rate
FROM retainflow.silver.fact_campaign_contact
GROUP BY campaign_type, channel_id
ORDER BY contacts DESC;

-- COMMAND ----------

SELECT *
FROM retainflow.silver.fact_quotes
ORDER BY quote_date DESC
LIMIT 100;

-- COMMAND ----------

SELECT
  quote_status,
  count(*) AS quotes,
  round(avg(quoted_annual_premium), 2) AS avg_quoted_annual_premium,
  round(avg(competitor_price_index), 4) AS avg_competitor_price_index
FROM retainflow.silver.fact_quotes
GROUP BY quote_status
ORDER BY quotes DESC;

-- COMMAND ----------

SELECT *
FROM retainflow.silver.fact_retention_actions
ORDER BY action_timestamp DESC
LIMIT 100;

-- COMMAND ----------

SELECT
  action_type,
  trigger_reason,
  count(*) AS actions,
  round(avg(CASE WHEN accepted_flag THEN 1.0 ELSE 0.0 END), 4) AS acceptance_rate,
  round(avg(CASE WHEN retained_90d_flag THEN 1.0 ELSE 0.0 END), 4) AS retained_90d_rate,
  round(avg(offered_value), 2) AS avg_offered_value
FROM retainflow.silver.fact_retention_actions
GROUP BY action_type, trigger_reason
ORDER BY actions DESC;

-- COMMAND ----------

SELECT
  c.customer_segment,
  count(*) AS actions,
  round(avg(a.offered_value), 2) AS avg_offered_value,
  round(avg(CASE WHEN a.accepted_flag THEN 1.0 ELSE 0.0 END), 4) AS acceptance_rate
FROM retainflow.silver.fact_retention_actions a
JOIN retainflow.silver.dim_customer c
  ON a.customer_id = c.customer_id
GROUP BY c.customer_segment
ORDER BY actions DESC;

-- COMMAND ----------

SELECT
  c.customer_id,
  c.first_name,
  c.last_name,
  c.customer_segment,
  c.estimated_income_band,
  c.digital_profile,
  count(DISTINCT p.policy_id) AS policy_count,
  round(sum(p.annual_premium), 2) AS total_annual_premium,
  count(DISTINCT CASE WHEN pay.payment_status IN ('LATE', 'REJECTED', 'WRITTEN_OFF') THEN pay.payment_id END) AS payment_incidents,
  max(p.premium_increase_pct_last_renewal) AS max_premium_increase_pct,
  min(p.next_renewal_date) AS next_renewal_date
FROM retainflow.silver.dim_customer c
LEFT JOIN retainflow.silver.fact_policy p
  ON c.customer_id = p.customer_id
LEFT JOIN retainflow.silver.fact_payments pay
  ON p.policy_id = pay.policy_id
GROUP BY
  c.customer_id,
  c.first_name,
  c.last_name,
  c.customer_segment,
  c.estimated_income_band,
  c.digital_profile
ORDER BY payment_incidents DESC, total_annual_premium DESC
LIMIT 100;

-- COMMAND ----------

SELECT *
FROM retainflow.gold.customer_360_snapshot
ORDER BY customer_value_score DESC
LIMIT 100;

-- COMMAND ----------

SELECT
  latent_churn_risk_band,
  count(*) AS customers,
  round(avg(customer_value_score), 3) AS avg_customer_value_score,
  round(avg(total_annual_premium), 2) AS avg_total_annual_premium,
  round(avg(payment_incidents_6m), 3) AS avg_payment_incidents_6m,
  round(avg(complaints_6m), 3) AS avg_complaints_6m,
  round(avg(avg_satisfaction_score_12m), 3) AS avg_satisfaction_score_12m
FROM retainflow.gold.customer_360_snapshot
GROUP BY latent_churn_risk_band
ORDER BY customers DESC;

-- COMMAND ----------

SELECT
  active_policy_count,
  number_of_products,
  count(*) AS customers,
  round(avg(customer_value_score), 3) AS avg_customer_value_score,
  round(avg(total_annual_premium), 2) AS avg_total_annual_premium
FROM retainflow.gold.customer_360_snapshot
GROUP BY active_policy_count, number_of_products
ORDER BY active_policy_count, number_of_products;

-- COMMAND ----------

SELECT *
FROM retainflow.ml.churn_feature_snapshot
LIMIT 100;

-- COMMAND ----------

SELECT *
FROM retainflow.ml.churn_labels
ORDER BY churn_probability DESC
LIMIT 100;

-- COMMAND ----------

SELECT
  churn_risk_band,
  count(*) AS customers,
  round(avg(churn_label), 4) AS churn_rate,
  round(avg(churn_probability), 4) AS avg_churn_probability
FROM retainflow.ml.churn_labels
GROUP BY churn_risk_band
ORDER BY avg_churn_probability DESC;

-- COMMAND ----------

SELECT
  label_reason,
  count(*) AS customers,
  round(avg(churn_label), 4) AS churn_rate,
  round(avg(churn_probability), 4) AS avg_churn_probability
FROM retainflow.ml.churn_labels
GROUP BY label_reason
ORDER BY customers DESC;

-- COMMAND ----------

SELECT
  f.customer_id,
  f.customer_segment,
  f.total_annual_premium,
  f.payment_incidents_6m,
  f.complaints_6m,
  f.avg_satisfaction_score_12m,
  f.renewal_days_min,
  l.churn_label,
  l.churn_probability,
  l.churn_risk_band,
  l.label_reason
FROM retainflow.ml.churn_feature_snapshot f
JOIN retainflow.ml.churn_labels l
  ON f.customer_id = l.customer_id
 AND f.observation_date = l.observation_date
ORDER BY l.churn_probability DESC
LIMIT 100;

-- COMMAND ----------

SELECT *
FROM retainflow.monitoring.logical_relationships
ORDER BY child_schema, child_table, relationship_id;

-- COMMAND ----------

SELECT *
FROM retainflow.monitoring.generation_batches
ORDER BY run_finished_at DESC
LIMIT 20;

-- COMMAND ----------

SELECT
  check_status,
  count(*) AS checks
FROM retainflow.monitoring.data_quality_results
GROUP BY check_status
ORDER BY check_status;

-- COMMAND ----------

SELECT
  schema_name,
  table_name,
  check_status,
  count(*) AS checks,
  sum(failed_row_count) AS failed_rows
FROM retainflow.monitoring.data_quality_results
GROUP BY schema_name, table_name, check_status
ORDER BY schema_name, table_name, check_status;

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

-- Zone libre : ecris tes propres requetes SQL ici.
SELECT current_catalog() AS current_catalog, current_schema() AS current_schema, current_user() AS current_user;
