-- RetainFlow - policy and policy event generation checks

WITH policy_checks AS (
  SELECT
    count(*) AS policy_count,
    count(DISTINCT customer_id) AS customers_with_policy,
    avg(annual_premium) AS avg_annual_premium,
    min(policy_start_date) AS min_policy_start_date,
    max(policy_start_date) AS max_policy_start_date,
    count(CASE WHEN policy_start_date > policy_end_date THEN 1 END) AS invalid_policy_date_count,
    count(CASE WHEN cancellation_date IS NOT NULL AND cancellation_date < policy_start_date THEN 1 END) AS invalid_cancellation_date_count
  FROM retainflow.silver.fact_policy
),
customer_count AS (
  SELECT count(*) AS customer_count
  FROM retainflow.silver.dim_customer
),
event_checks AS (
  SELECT
    count(*) AS policy_event_count,
    count(CASE WHEN event_date IS NULL THEN 1 END) AS null_event_date_count
  FROM retainflow.silver.fact_policy_events
),
duplicate_policies AS (
  SELECT count(*) AS duplicate_policy_id_count
  FROM (
    SELECT policy_id
    FROM retainflow.silver.fact_policy
    GROUP BY policy_id
    HAVING count(*) > 1
  )
),
duplicate_policy_events AS (
  SELECT count(*) AS duplicate_policy_event_id_count
  FROM (
    SELECT policy_event_id
    FROM retainflow.silver.fact_policy_events
    GROUP BY policy_event_id
    HAVING count(*) > 1
  )
),
orphan_policy_customer AS (
  SELECT count(*) AS orphan_policy_customer_count
  FROM retainflow.silver.fact_policy p
  LEFT JOIN retainflow.silver.dim_customer c
    ON p.customer_id = c.customer_id
  WHERE c.customer_id IS NULL
),
orphan_policy_product AS (
  SELECT count(*) AS orphan_policy_product_count
  FROM retainflow.silver.fact_policy p
  LEFT JOIN retainflow.silver.dim_product pr
    ON p.product_id = pr.product_id
  WHERE pr.product_id IS NULL
),
orphan_policy_channel AS (
  SELECT count(*) AS orphan_policy_channel_count
  FROM retainflow.silver.fact_policy p
  LEFT JOIN retainflow.silver.dim_channel ch
    ON p.sales_channel_id = ch.channel_id
  WHERE ch.channel_id IS NULL
),
orphan_policy_agent AS (
  SELECT count(*) AS orphan_policy_agent_count
  FROM retainflow.silver.fact_policy p
  LEFT JOIN retainflow.silver.dim_agent a
    ON p.agent_id = a.agent_id
  WHERE p.agent_id IS NOT NULL
    AND a.agent_id IS NULL
),
orphan_event_policy AS (
  SELECT count(*) AS orphan_event_policy_count
  FROM retainflow.silver.fact_policy_events e
  LEFT JOIN retainflow.silver.fact_policy p
    ON e.policy_id = p.policy_id
  WHERE p.policy_id IS NULL
)
SELECT 'customer_count' AS metric, CAST(customer_count AS STRING) AS value FROM customer_count
UNION ALL SELECT 'policy_count', CAST(policy_count AS STRING) FROM policy_checks
UNION ALL SELECT 'customers_with_policy', CAST(customers_with_policy AS STRING) FROM policy_checks
UNION ALL SELECT 'avg_policies_per_customer', CAST(round(policy_count / customer_count, 4) AS STRING) FROM policy_checks CROSS JOIN customer_count
UNION ALL SELECT 'avg_annual_premium', CAST(round(avg_annual_premium, 2) AS STRING) FROM policy_checks
UNION ALL SELECT 'min_policy_start_date', CAST(min_policy_start_date AS STRING) FROM policy_checks
UNION ALL SELECT 'max_policy_start_date', CAST(max_policy_start_date AS STRING) FROM policy_checks
UNION ALL SELECT 'policy_event_count', CAST(policy_event_count AS STRING) FROM event_checks
UNION ALL SELECT 'null_event_date_count', CAST(null_event_date_count AS STRING) FROM event_checks
UNION ALL SELECT 'invalid_policy_date_count', CAST(invalid_policy_date_count AS STRING) FROM policy_checks
UNION ALL SELECT 'invalid_cancellation_date_count', CAST(invalid_cancellation_date_count AS STRING) FROM policy_checks
UNION ALL SELECT 'duplicate_policy_id_count', CAST(duplicate_policy_id_count AS STRING) FROM duplicate_policies
UNION ALL SELECT 'duplicate_policy_event_id_count', CAST(duplicate_policy_event_id_count AS STRING) FROM duplicate_policy_events
UNION ALL SELECT 'orphan_policy_customer_count', CAST(orphan_policy_customer_count AS STRING) FROM orphan_policy_customer
UNION ALL SELECT 'orphan_policy_product_count', CAST(orphan_policy_product_count AS STRING) FROM orphan_policy_product
UNION ALL SELECT 'orphan_policy_channel_count', CAST(orphan_policy_channel_count AS STRING) FROM orphan_policy_channel
UNION ALL SELECT 'orphan_policy_agent_count', CAST(orphan_policy_agent_count AS STRING) FROM orphan_policy_agent
UNION ALL SELECT 'orphan_event_policy_count', CAST(orphan_event_policy_count AS STRING) FROM orphan_event_policy
ORDER BY metric;

SELECT policy_status, count(*) AS policies
FROM retainflow.silver.fact_policy
GROUP BY policy_status
ORDER BY policies DESC;

SELECT p.product_family, count(*) AS policies
FROM retainflow.silver.fact_policy f
JOIN retainflow.silver.dim_product p
  ON f.product_id = p.product_id
GROUP BY p.product_family
ORDER BY policies DESC;

SELECT event_type, count(*) AS events
FROM retainflow.silver.fact_policy_events
GROUP BY event_type
ORDER BY events DESC;
