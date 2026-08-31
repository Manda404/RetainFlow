-- RetainFlow - retention action generation checks

WITH action_checks AS (
  SELECT
    count(*) AS retention_action_count,
    count(DISTINCT customer_id) AS customers_with_retention_action,
    avg(CASE WHEN accepted_flag THEN 1.0 ELSE 0.0 END) AS acceptance_rate,
    avg(CASE WHEN retained_90d_flag THEN 1.0 ELSE 0.0 END) AS retained_90d_rate,
    avg(offered_value) AS avg_offered_value,
    min(action_date) AS min_action_date,
    max(action_date) AS max_action_date,
    count(CASE WHEN offered_value < 0 THEN 1 END) AS negative_offered_value_count,
    count(CASE WHEN action_type NOT IN ('DISCOUNT', 'COVERAGE_UPGRADE', 'CALLBACK', 'PAYMENT_PLAN', 'LOYALTY_BONUS', 'CLAIM_REVIEW') THEN 1 END) AS invalid_action_type_count,
    count(CASE WHEN trigger_reason NOT IN ('PREMIUM_INCREASE', 'COMPLAINT', 'PAYMENT_INCIDENT', 'LOW_ENGAGEMENT', 'RENEWAL_RISK', 'HIGH_VALUE_SAVE', 'POOR_CLAIM_EXPERIENCE') THEN 1 END) AS invalid_trigger_reason_count
  FROM retainflow.silver.fact_retention_actions
),
customer_count AS (
  SELECT count(*) AS customer_count
  FROM retainflow.silver.dim_customer
),
duplicate_actions AS (
  SELECT count(*) AS duplicate_retention_action_id_count
  FROM (
    SELECT retention_action_id
    FROM retainflow.silver.fact_retention_actions
    GROUP BY retention_action_id
    HAVING count(*) > 1
  )
),
orphan_action_customer AS (
  SELECT count(*) AS orphan_retention_customer_count
  FROM retainflow.silver.fact_retention_actions a
  LEFT JOIN retainflow.silver.dim_customer c
    ON a.customer_id = c.customer_id
  WHERE c.customer_id IS NULL
),
orphan_action_policy AS (
  SELECT count(*) AS orphan_retention_policy_count
  FROM retainflow.silver.fact_retention_actions a
  LEFT JOIN retainflow.silver.fact_policy p
    ON a.policy_id = p.policy_id
  WHERE a.policy_id IS NOT NULL
    AND p.policy_id IS NULL
),
orphan_action_channel AS (
  SELECT count(*) AS orphan_retention_channel_count
  FROM retainflow.silver.fact_retention_actions a
  LEFT JOIN retainflow.silver.dim_channel ch
    ON a.channel_id = ch.channel_id
  WHERE ch.channel_id IS NULL
),
orphan_action_agent AS (
  SELECT count(*) AS orphan_retention_agent_count
  FROM retainflow.silver.fact_retention_actions a
  LEFT JOIN retainflow.silver.dim_agent ag
    ON a.agent_id = ag.agent_id
  WHERE a.agent_id IS NOT NULL
    AND ag.agent_id IS NULL
)
SELECT 'customer_count' AS metric, CAST(customer_count AS STRING) AS value FROM customer_count
UNION ALL SELECT 'retention_action_count', CAST(retention_action_count AS STRING) FROM action_checks
UNION ALL SELECT 'customers_with_retention_action', CAST(customers_with_retention_action AS STRING) FROM action_checks
UNION ALL SELECT 'retention_action_rate_per_customer', CAST(round(retention_action_count / customer_count, 4) AS STRING) FROM action_checks CROSS JOIN customer_count
UNION ALL SELECT 'acceptance_rate', CAST(round(acceptance_rate, 4) AS STRING) FROM action_checks
UNION ALL SELECT 'retained_90d_rate', CAST(round(retained_90d_rate, 4) AS STRING) FROM action_checks
UNION ALL SELECT 'avg_offered_value', CAST(round(avg_offered_value, 2) AS STRING) FROM action_checks
UNION ALL SELECT 'min_action_date', CAST(min_action_date AS STRING) FROM action_checks
UNION ALL SELECT 'max_action_date', CAST(max_action_date AS STRING) FROM action_checks
UNION ALL SELECT 'negative_offered_value_count', CAST(negative_offered_value_count AS STRING) FROM action_checks
UNION ALL SELECT 'invalid_action_type_count', CAST(invalid_action_type_count AS STRING) FROM action_checks
UNION ALL SELECT 'invalid_trigger_reason_count', CAST(invalid_trigger_reason_count AS STRING) FROM action_checks
UNION ALL SELECT 'duplicate_retention_action_id_count', CAST(duplicate_retention_action_id_count AS STRING) FROM duplicate_actions
UNION ALL SELECT 'orphan_retention_customer_count', CAST(orphan_retention_customer_count AS STRING) FROM orphan_action_customer
UNION ALL SELECT 'orphan_retention_policy_count', CAST(orphan_retention_policy_count AS STRING) FROM orphan_action_policy
UNION ALL SELECT 'orphan_retention_channel_count', CAST(orphan_retention_channel_count AS STRING) FROM orphan_action_channel
UNION ALL SELECT 'orphan_retention_agent_count', CAST(orphan_retention_agent_count AS STRING) FROM orphan_action_agent
ORDER BY metric;

SELECT action_type, trigger_reason, count(*) AS actions, round(avg(CASE WHEN accepted_flag THEN 1.0 ELSE 0.0 END), 4) AS acceptance_rate
FROM retainflow.silver.fact_retention_actions
GROUP BY action_type, trigger_reason
ORDER BY actions DESC;

SELECT channel_id, count(*) AS actions, round(avg(CASE WHEN accepted_flag THEN 1.0 ELSE 0.0 END), 4) AS acceptance_rate
FROM retainflow.silver.fact_retention_actions
GROUP BY channel_id
ORDER BY actions DESC;

SELECT c.customer_segment, count(*) AS actions, round(avg(a.offered_value), 2) AS avg_offered_value
FROM retainflow.silver.fact_retention_actions a
JOIN retainflow.silver.dim_customer c
  ON a.customer_id = c.customer_id
GROUP BY c.customer_segment
ORDER BY actions DESC;
