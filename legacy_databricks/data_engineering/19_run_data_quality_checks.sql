-- RetainFlow - persist data quality checks
-- Run after 21_build_ml_churn_dataset.sql.

DELETE FROM retainflow.monitoring.data_quality_results;

INSERT INTO retainflow.monitoring.data_quality_results
WITH latest_batch AS (
  SELECT coalesce(max_by(batch_id, run_finished_at), 'MANUAL_DQ_RUN') AS batch_id
  FROM retainflow.monitoring.generation_batches
),
config AS (
  SELECT n_customers
  FROM retainflow.monitoring.generation_config
  WHERE is_active = true
),
checks AS (
  SELECT 'silver' AS schema_name, 'dim_customer' AS table_name, 'row_count_matches_config' AS check_name, 'ROW_COUNT' AS check_type, abs(count(*) - max(cfg.n_customers)) AS failed_row_count, count(*) AS observed_value, max(cfg.n_customers) AS expected_value, 'Customer count should match active generation config.' AS check_message
  FROM retainflow.silver.dim_customer c CROSS JOIN config cfg
  UNION ALL
  SELECT 'gold', 'customer_360_snapshot', 'row_count_matches_customers', 'ROW_COUNT', abs(count(*) - max(cfg.n_customers)), count(*), max(cfg.n_customers), 'Customer 360 should contain one row per customer.'
  FROM retainflow.gold.customer_360_snapshot g CROSS JOIN config cfg
  UNION ALL
  SELECT 'silver', 'dim_customer', 'duplicate_customer_id', 'PK_UNIQUENESS', count(*), count(*), 0, 'customer_id must be unique.'
  FROM (SELECT customer_id FROM retainflow.silver.dim_customer GROUP BY customer_id HAVING count(*) > 1)
  UNION ALL
  SELECT 'silver', 'fact_policy', 'duplicate_policy_id', 'PK_UNIQUENESS', count(*), count(*), 0, 'policy_id must be unique.'
  FROM (SELECT policy_id FROM retainflow.silver.fact_policy GROUP BY policy_id HAVING count(*) > 1)
  UNION ALL
  SELECT 'silver', 'fact_policy_events', 'duplicate_policy_event_id', 'PK_UNIQUENESS', count(*), count(*), 0, 'policy_event_id must be unique.'
  FROM (SELECT policy_event_id FROM retainflow.silver.fact_policy_events GROUP BY policy_event_id HAVING count(*) > 1)
  UNION ALL
  SELECT 'silver', 'fact_payments', 'duplicate_payment_id', 'PK_UNIQUENESS', count(*), count(*), 0, 'payment_id must be unique.'
  FROM (SELECT payment_id FROM retainflow.silver.fact_payments GROUP BY payment_id HAVING count(*) > 1)
  UNION ALL
  SELECT 'silver', 'fact_claims', 'duplicate_claim_id', 'PK_UNIQUENESS', count(*), count(*), 0, 'claim_id must be unique.'
  FROM (SELECT claim_id FROM retainflow.silver.fact_claims GROUP BY claim_id HAVING count(*) > 1)
  UNION ALL
  SELECT 'silver', 'fact_interactions', 'duplicate_interaction_id', 'PK_UNIQUENESS', count(*), count(*), 0, 'interaction_id must be unique.'
  FROM (SELECT interaction_id FROM retainflow.silver.fact_interactions GROUP BY interaction_id HAVING count(*) > 1)
  UNION ALL
  SELECT 'silver', 'fact_customer_service', 'duplicate_case_id', 'PK_UNIQUENESS', count(*), count(*), 0, 'case_id must be unique.'
  FROM (SELECT case_id FROM retainflow.silver.fact_customer_service GROUP BY case_id HAVING count(*) > 1)
  UNION ALL
  SELECT 'silver', 'fact_campaign_contact', 'duplicate_campaign_contact_id', 'PK_UNIQUENESS', count(*), count(*), 0, 'campaign_contact_id must be unique.'
  FROM (SELECT campaign_contact_id FROM retainflow.silver.fact_campaign_contact GROUP BY campaign_contact_id HAVING count(*) > 1)
  UNION ALL
  SELECT 'silver', 'fact_quotes', 'duplicate_quote_id', 'PK_UNIQUENESS', count(*), count(*), 0, 'quote_id must be unique.'
  FROM (SELECT quote_id FROM retainflow.silver.fact_quotes GROUP BY quote_id HAVING count(*) > 1)
  UNION ALL
  SELECT 'silver', 'fact_retention_actions', 'duplicate_retention_action_id', 'PK_UNIQUENESS', count(*), count(*), 0, 'retention_action_id must be unique.'
  FROM (SELECT retention_action_id FROM retainflow.silver.fact_retention_actions GROUP BY retention_action_id HAVING count(*) > 1)
  UNION ALL
  SELECT 'gold', 'customer_360_snapshot', 'duplicate_customer_360_key', 'PK_UNIQUENESS', count(*), count(*), 0, 'observation_date and customer_id must be unique.'
  FROM (SELECT observation_date, customer_id FROM retainflow.gold.customer_360_snapshot GROUP BY observation_date, customer_id HAVING count(*) > 1)
  UNION ALL
  SELECT 'ml', 'churn_feature_snapshot', 'duplicate_feature_key', 'PK_UNIQUENESS', count(*), count(*), 0, 'observation_date and customer_id must be unique.'
  FROM (SELECT observation_date, customer_id FROM retainflow.ml.churn_feature_snapshot GROUP BY observation_date, customer_id HAVING count(*) > 1)
  UNION ALL
  SELECT 'ml', 'churn_labels', 'duplicate_label_key', 'PK_UNIQUENESS', count(*), count(*), 0, 'observation_date and customer_id must be unique.'
  FROM (SELECT observation_date, customer_id FROM retainflow.ml.churn_labels GROUP BY observation_date, customer_id HAVING count(*) > 1)
  UNION ALL
  SELECT 'silver', 'fact_policy', 'orphan_customer_id', 'FK_ORPHAN', count(*), count(*), 0, 'Policies must reference existing customers.'
  FROM retainflow.silver.fact_policy p LEFT JOIN retainflow.silver.dim_customer c ON p.customer_id = c.customer_id WHERE c.customer_id IS NULL
  UNION ALL
  SELECT 'silver', 'fact_policy', 'orphan_product_id', 'FK_ORPHAN', count(*), count(*), 0, 'Policies must reference existing products.'
  FROM retainflow.silver.fact_policy p LEFT JOIN retainflow.silver.dim_product pr ON p.product_id = pr.product_id WHERE pr.product_id IS NULL
  UNION ALL
  SELECT 'silver', 'fact_policy', 'orphan_sales_channel_id', 'FK_ORPHAN', count(*), count(*), 0, 'Policies must reference existing sales channels.'
  FROM retainflow.silver.fact_policy p LEFT JOIN retainflow.silver.dim_channel ch ON p.sales_channel_id = ch.channel_id WHERE ch.channel_id IS NULL
  UNION ALL
  SELECT 'silver', 'fact_policy_events', 'orphan_policy_id', 'FK_ORPHAN', count(*), count(*), 0, 'Policy events must reference existing policies.'
  FROM retainflow.silver.fact_policy_events e LEFT JOIN retainflow.silver.fact_policy p ON e.policy_id = p.policy_id WHERE p.policy_id IS NULL
  UNION ALL
  SELECT 'silver', 'fact_payments', 'orphan_policy_id', 'FK_ORPHAN', count(*), count(*), 0, 'Payments must reference existing policies.'
  FROM retainflow.silver.fact_payments pay LEFT JOIN retainflow.silver.fact_policy p ON pay.policy_id = p.policy_id WHERE p.policy_id IS NULL
  UNION ALL
  SELECT 'silver', 'fact_claims', 'orphan_policy_id', 'FK_ORPHAN', count(*), count(*), 0, 'Claims must reference existing policies.'
  FROM retainflow.silver.fact_claims clm LEFT JOIN retainflow.silver.fact_policy p ON clm.policy_id = p.policy_id WHERE p.policy_id IS NULL
  UNION ALL
  SELECT 'silver', 'fact_interactions', 'orphan_customer_id', 'FK_ORPHAN', count(*), count(*), 0, 'Interactions must reference existing customers.'
  FROM retainflow.silver.fact_interactions i LEFT JOIN retainflow.silver.dim_customer c ON i.customer_id = c.customer_id WHERE c.customer_id IS NULL
  UNION ALL
  SELECT 'silver', 'fact_customer_service', 'orphan_interaction_id', 'FK_ORPHAN', count(*), count(*), 0, 'Service cases with interaction_id must reference existing interactions.'
  FROM retainflow.silver.fact_customer_service cs LEFT JOIN retainflow.silver.fact_interactions i ON cs.interaction_id = i.interaction_id WHERE cs.interaction_id IS NOT NULL AND i.interaction_id IS NULL
  UNION ALL
  SELECT 'silver', 'fact_campaign_contact', 'orphan_customer_id', 'FK_ORPHAN', count(*), count(*), 0, 'Campaign contacts must reference existing customers.'
  FROM retainflow.silver.fact_campaign_contact cc LEFT JOIN retainflow.silver.dim_customer c ON cc.customer_id = c.customer_id WHERE c.customer_id IS NULL
  UNION ALL
  SELECT 'silver', 'fact_quotes', 'orphan_product_id', 'FK_ORPHAN', count(*), count(*), 0, 'Quotes must reference existing products.'
  FROM retainflow.silver.fact_quotes q LEFT JOIN retainflow.silver.dim_product p ON q.product_id = p.product_id WHERE p.product_id IS NULL
  UNION ALL
  SELECT 'silver', 'fact_retention_actions', 'orphan_policy_id', 'FK_ORPHAN', count(*), count(*), 0, 'Retention actions must reference existing policies.'
  FROM retainflow.silver.fact_retention_actions a LEFT JOIN retainflow.silver.fact_policy p ON a.policy_id = p.policy_id WHERE a.policy_id IS NOT NULL AND p.policy_id IS NULL
  UNION ALL
  SELECT 'gold', 'customer_360_snapshot', 'orphan_customer_id', 'FK_ORPHAN', count(*), count(*), 0, 'Gold Customer 360 must reference existing customers.'
  FROM retainflow.gold.customer_360_snapshot g LEFT JOIN retainflow.silver.dim_customer c ON g.customer_id = c.customer_id WHERE c.customer_id IS NULL
  UNION ALL
  SELECT 'ml', 'churn_feature_snapshot', 'orphan_customer_id', 'FK_ORPHAN', count(*), count(*), 0, 'ML feature rows must reference existing customers.'
  FROM retainflow.ml.churn_feature_snapshot f LEFT JOIN retainflow.silver.dim_customer c ON f.customer_id = c.customer_id WHERE c.customer_id IS NULL
  UNION ALL
  SELECT 'ml', 'churn_labels', 'orphan_customer_id', 'FK_ORPHAN', count(*), count(*), 0, 'ML label rows must reference existing customers.'
  FROM retainflow.ml.churn_labels l LEFT JOIN retainflow.silver.dim_customer c ON l.customer_id = c.customer_id WHERE c.customer_id IS NULL
  UNION ALL
  SELECT 'ml', 'churn_feature_snapshot', 'missing_label_for_feature', 'RELATIONSHIP', count(*), count(*), 0, 'Each ML feature row must have one matching label row.'
  FROM retainflow.ml.churn_feature_snapshot f
  LEFT JOIN retainflow.ml.churn_labels l
    ON f.customer_id = l.customer_id
   AND f.observation_date = l.observation_date
  WHERE l.customer_id IS NULL
  UNION ALL
  SELECT 'ml', 'churn_labels', 'missing_feature_for_label', 'RELATIONSHIP', count(*), count(*), 0, 'Each ML label row must have one matching feature row.'
  FROM retainflow.ml.churn_labels l
  LEFT JOIN retainflow.ml.churn_feature_snapshot f
    ON l.customer_id = f.customer_id
   AND l.observation_date = f.observation_date
  WHERE f.customer_id IS NULL
  UNION ALL
  SELECT 'silver', 'fact_policy', 'invalid_policy_dates', 'RANGE', count(*), count(*), 0, 'Policy start date must be before policy end date.'
  FROM retainflow.silver.fact_policy WHERE policy_start_date > policy_end_date
  UNION ALL
  SELECT 'silver', 'fact_claims', 'invalid_claim_amounts', 'RANGE', count(*), count(*), 0, 'Claim amounts must be positive and paid amounts cannot exceed claim amounts.'
  FROM retainflow.silver.fact_claims WHERE claim_amount <= 0 OR paid_amount < 0 OR paid_amount > claim_amount
  UNION ALL
  SELECT 'silver', 'fact_payments', 'invalid_payment_amounts', 'RANGE', count(*), count(*), 0, 'Payment amounts must be positive.'
  FROM retainflow.silver.fact_payments WHERE payment_amount <= 0
  UNION ALL
  SELECT 'silver', 'fact_interactions', 'invalid_interaction_scores', 'RANGE', count(*), count(*), 0, 'Interaction duration and sentiment must be valid.'
  FROM retainflow.silver.fact_interactions WHERE duration_seconds <= 0 OR sentiment_score < -1 OR sentiment_score > 1
  UNION ALL
  SELECT 'silver', 'fact_customer_service', 'invalid_service_scores', 'RANGE', count(*), count(*), 0, 'Service satisfaction must be between 1 and 5.'
  FROM retainflow.silver.fact_customer_service WHERE satisfaction_score < 1 OR satisfaction_score > 5
  UNION ALL
  SELECT 'silver', 'fact_quotes', 'invalid_quote_values', 'RANGE', count(*), count(*), 0, 'Quote amount and competitor price index must be positive.'
  FROM retainflow.silver.fact_quotes WHERE quoted_annual_premium <= 0 OR competitor_price_index <= 0
  UNION ALL
  SELECT 'gold', 'customer_360_snapshot', 'invalid_gold_metrics', 'RANGE', count(*), count(*), 0, 'Gold metrics must be non-negative and bounded where applicable.'
  FROM retainflow.gold.customer_360_snapshot
  WHERE tenure_months < 0
     OR active_policy_count < 0
     OR total_annual_premium < 0
     OR email_open_rate_6m < 0
     OR email_open_rate_6m > 1
     OR avg_satisfaction_score_12m < 1
     OR avg_satisfaction_score_12m > 5
  UNION ALL
  SELECT 'ml', 'churn_feature_snapshot', 'invalid_feature_values', 'RANGE', count(*), count(*), 0, 'ML feature values must be in valid ranges.'
  FROM retainflow.ml.churn_feature_snapshot
  WHERE tenure_months < 0
     OR active_policy_count < 0
     OR total_annual_premium < 0
     OR email_open_rate_6m < 0
     OR email_open_rate_6m > 1
     OR avg_satisfaction_score_12m < 1
     OR avg_satisfaction_score_12m > 5
  UNION ALL
  SELECT 'ml', 'churn_labels', 'invalid_label_values', 'RANGE', count(*), count(*), 0, 'ML label values must be binary and probabilities must be between 0 and 1.'
  FROM retainflow.ml.churn_labels
  WHERE churn_label NOT IN (0, 1)
     OR churn_probability < 0
     OR churn_probability > 1
)
SELECT
  concat('DQ_', substr(sha2(concat_ws('|', lb.batch_id, schema_name, table_name, check_name), 256), 1, 24)) AS dq_result_id,
  lb.batch_id,
  'retainflow' AS catalog_name,
  schema_name,
  table_name,
  check_name,
  check_type,
  CASE WHEN failed_row_count = 0 THEN 'PASS' ELSE 'FAIL' END AS check_status,
  CAST(observed_value AS DOUBLE) AS observed_value,
  CAST(expected_value AS DOUBLE) AS expected_value,
  CAST(0 AS DOUBLE) AS threshold_value,
  CAST(failed_row_count AS BIGINT) AS failed_row_count,
  check_message,
  current_timestamp() AS checked_at
FROM checks
CROSS JOIN latest_batch lb;
