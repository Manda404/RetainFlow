-- RetainFlow - interactions and customer service generation checks

WITH interaction_checks AS (
  SELECT
    count(*) AS interaction_count,
    count(DISTINCT customer_id) AS customers_with_interaction,
    avg(duration_seconds) AS avg_duration_seconds,
    avg(sentiment_score) AS avg_sentiment_score,
    min(interaction_datetime) AS min_interaction_datetime,
    max(interaction_datetime) AS max_interaction_datetime,
    count(CASE WHEN duration_seconds <= 0 THEN 1 END) AS non_positive_duration_count,
    count(CASE WHEN sentiment_score < -1 OR sentiment_score > 1 THEN 1 END) AS invalid_sentiment_count
  FROM retainflow.silver.fact_interactions
),
service_checks AS (
  SELECT
    count(*) AS service_case_count,
    count(DISTINCT customer_id) AS customers_with_service_case,
    avg(satisfaction_score) AS avg_service_satisfaction,
    count(CASE WHEN closed_datetime IS NOT NULL AND closed_datetime < opened_datetime THEN 1 END) AS close_before_open_count,
    count(CASE WHEN satisfaction_score < 1 OR satisfaction_score > 5 THEN 1 END) AS invalid_satisfaction_count
  FROM retainflow.silver.fact_customer_service
),
customer_count AS (
  SELECT count(*) AS customer_count
  FROM retainflow.silver.dim_customer
),
duplicate_interactions AS (
  SELECT count(*) AS duplicate_interaction_id_count
  FROM (
    SELECT interaction_id
    FROM retainflow.silver.fact_interactions
    GROUP BY interaction_id
    HAVING count(*) > 1
  )
),
duplicate_cases AS (
  SELECT count(*) AS duplicate_case_id_count
  FROM (
    SELECT case_id
    FROM retainflow.silver.fact_customer_service
    GROUP BY case_id
    HAVING count(*) > 1
  )
),
orphan_interaction_customer AS (
  SELECT count(*) AS orphan_interaction_customer_count
  FROM retainflow.silver.fact_interactions i
  LEFT JOIN retainflow.silver.dim_customer c
    ON i.customer_id = c.customer_id
  WHERE c.customer_id IS NULL
),
orphan_interaction_policy AS (
  SELECT count(*) AS orphan_interaction_policy_count
  FROM retainflow.silver.fact_interactions i
  LEFT JOIN retainflow.silver.fact_policy p
    ON i.policy_id = p.policy_id
  WHERE i.policy_id IS NOT NULL
    AND p.policy_id IS NULL
),
orphan_interaction_channel AS (
  SELECT count(*) AS orphan_interaction_channel_count
  FROM retainflow.silver.fact_interactions i
  LEFT JOIN retainflow.silver.dim_channel ch
    ON i.channel_id = ch.channel_id
  WHERE ch.channel_id IS NULL
),
orphan_interaction_agent AS (
  SELECT count(*) AS orphan_interaction_agent_count
  FROM retainflow.silver.fact_interactions i
  LEFT JOIN retainflow.silver.dim_agent a
    ON i.agent_id = a.agent_id
  WHERE i.agent_id IS NOT NULL
    AND a.agent_id IS NULL
),
orphan_case_interaction AS (
  SELECT count(*) AS orphan_case_interaction_count
  FROM retainflow.silver.fact_customer_service cs
  LEFT JOIN retainflow.silver.fact_interactions i
    ON cs.interaction_id = i.interaction_id
  WHERE cs.interaction_id IS NOT NULL
    AND i.interaction_id IS NULL
),
orphan_case_customer AS (
  SELECT count(*) AS orphan_case_customer_count
  FROM retainflow.silver.fact_customer_service cs
  LEFT JOIN retainflow.silver.dim_customer c
    ON cs.customer_id = c.customer_id
  WHERE c.customer_id IS NULL
)
SELECT 'customer_count' AS metric, CAST(customer_count AS STRING) AS value FROM customer_count
UNION ALL SELECT 'interaction_count', CAST(interaction_count AS STRING) FROM interaction_checks
UNION ALL SELECT 'customers_with_interaction', CAST(customers_with_interaction AS STRING) FROM interaction_checks
UNION ALL SELECT 'avg_interactions_per_customer', CAST(round(interaction_count / customer_count, 4) AS STRING) FROM interaction_checks CROSS JOIN customer_count
UNION ALL SELECT 'avg_duration_seconds', CAST(round(avg_duration_seconds, 2) AS STRING) FROM interaction_checks
UNION ALL SELECT 'avg_sentiment_score', CAST(round(avg_sentiment_score, 4) AS STRING) FROM interaction_checks
UNION ALL SELECT 'min_interaction_datetime', CAST(min_interaction_datetime AS STRING) FROM interaction_checks
UNION ALL SELECT 'max_interaction_datetime', CAST(max_interaction_datetime AS STRING) FROM interaction_checks
UNION ALL SELECT 'service_case_count', CAST(service_case_count AS STRING) FROM service_checks
UNION ALL SELECT 'customers_with_service_case', CAST(customers_with_service_case AS STRING) FROM service_checks
UNION ALL SELECT 'avg_service_satisfaction', CAST(round(avg_service_satisfaction, 3) AS STRING) FROM service_checks
UNION ALL SELECT 'non_positive_duration_count', CAST(non_positive_duration_count AS STRING) FROM interaction_checks
UNION ALL SELECT 'invalid_sentiment_count', CAST(invalid_sentiment_count AS STRING) FROM interaction_checks
UNION ALL SELECT 'close_before_open_count', CAST(close_before_open_count AS STRING) FROM service_checks
UNION ALL SELECT 'invalid_satisfaction_count', CAST(invalid_satisfaction_count AS STRING) FROM service_checks
UNION ALL SELECT 'duplicate_interaction_id_count', CAST(duplicate_interaction_id_count AS STRING) FROM duplicate_interactions
UNION ALL SELECT 'duplicate_case_id_count', CAST(duplicate_case_id_count AS STRING) FROM duplicate_cases
UNION ALL SELECT 'orphan_interaction_customer_count', CAST(orphan_interaction_customer_count AS STRING) FROM orphan_interaction_customer
UNION ALL SELECT 'orphan_interaction_policy_count', CAST(orphan_interaction_policy_count AS STRING) FROM orphan_interaction_policy
UNION ALL SELECT 'orphan_interaction_channel_count', CAST(orphan_interaction_channel_count AS STRING) FROM orphan_interaction_channel
UNION ALL SELECT 'orphan_interaction_agent_count', CAST(orphan_interaction_agent_count AS STRING) FROM orphan_interaction_agent
UNION ALL SELECT 'orphan_case_interaction_count', CAST(orphan_case_interaction_count AS STRING) FROM orphan_case_interaction
UNION ALL SELECT 'orphan_case_customer_count', CAST(orphan_case_customer_count AS STRING) FROM orphan_case_customer
ORDER BY metric;

SELECT channel_id, interaction_type, count(*) AS interactions
FROM retainflow.silver.fact_interactions
GROUP BY channel_id, interaction_type
ORDER BY interactions DESC;

SELECT interaction_reason, direction, count(*) AS interactions, round(avg(sentiment_score), 4) AS avg_sentiment
FROM retainflow.silver.fact_interactions
GROUP BY interaction_reason, direction
ORDER BY interactions DESC;

SELECT case_type, priority, count(*) AS service_cases, round(avg(satisfaction_score), 3) AS avg_satisfaction
FROM retainflow.silver.fact_customer_service
GROUP BY case_type, priority
ORDER BY service_cases DESC;
