-- RetainFlow - ML churn dataset checks

WITH feature_checks AS (
  SELECT
    count(*) AS feature_count,
    count(DISTINCT customer_id) AS feature_customers,
    min(observation_date) AS min_observation_date,
    max(observation_date) AS max_observation_date,
    count(CASE WHEN total_annual_premium < 0 THEN 1 END) AS negative_premium_count,
    count(CASE WHEN email_open_rate_6m < 0 OR email_open_rate_6m > 1 THEN 1 END) AS invalid_email_open_rate_count,
    count(CASE WHEN avg_satisfaction_score_12m < 1 OR avg_satisfaction_score_12m > 5 THEN 1 END) AS invalid_satisfaction_count
  FROM retainflow.ml.churn_feature_snapshot
),
label_checks AS (
  SELECT
    count(*) AS label_count,
    count(DISTINCT customer_id) AS label_customers,
    avg(churn_label) AS churn_rate,
    avg(churn_probability) AS avg_churn_probability,
    min(churn_probability) AS min_churn_probability,
    max(churn_probability) AS max_churn_probability,
    count(CASE WHEN churn_label NOT IN (0, 1) THEN 1 END) AS invalid_churn_label_count,
    count(CASE WHEN churn_probability < 0 OR churn_probability > 1 THEN 1 END) AS invalid_churn_probability_count
  FROM retainflow.ml.churn_labels
),
customer_count AS (
  SELECT count(*) AS customer_count
  FROM retainflow.silver.dim_customer
),
duplicate_features AS (
  SELECT count(*) AS duplicate_feature_key_count
  FROM (
    SELECT observation_date, customer_id
    FROM retainflow.ml.churn_feature_snapshot
    GROUP BY observation_date, customer_id
    HAVING count(*) > 1
  )
),
duplicate_labels AS (
  SELECT count(*) AS duplicate_label_key_count
  FROM (
    SELECT observation_date, customer_id
    FROM retainflow.ml.churn_labels
    GROUP BY observation_date, customer_id
    HAVING count(*) > 1
  )
),
orphan_feature_customer AS (
  SELECT count(*) AS orphan_feature_customer_count
  FROM retainflow.ml.churn_feature_snapshot f
  LEFT JOIN retainflow.silver.dim_customer c
    ON f.customer_id = c.customer_id
  WHERE c.customer_id IS NULL
),
orphan_label_customer AS (
  SELECT count(*) AS orphan_label_customer_count
  FROM retainflow.ml.churn_labels l
  LEFT JOIN retainflow.silver.dim_customer c
    ON l.customer_id = c.customer_id
  WHERE c.customer_id IS NULL
),
missing_label_for_feature AS (
  SELECT count(*) AS missing_label_for_feature_count
  FROM retainflow.ml.churn_feature_snapshot f
  LEFT JOIN retainflow.ml.churn_labels l
    ON f.customer_id = l.customer_id
   AND f.observation_date = l.observation_date
  WHERE l.customer_id IS NULL
),
missing_feature_for_label AS (
  SELECT count(*) AS missing_feature_for_label_count
  FROM retainflow.ml.churn_labels l
  LEFT JOIN retainflow.ml.churn_feature_snapshot f
    ON l.customer_id = f.customer_id
   AND l.observation_date = f.observation_date
  WHERE f.customer_id IS NULL
)
SELECT 'customer_count' AS metric, CAST(customer_count AS STRING) AS value FROM customer_count
UNION ALL SELECT 'feature_count', CAST(feature_count AS STRING) FROM feature_checks
UNION ALL SELECT 'feature_customers', CAST(feature_customers AS STRING) FROM feature_checks
UNION ALL SELECT 'label_count', CAST(label_count AS STRING) FROM label_checks
UNION ALL SELECT 'label_customers', CAST(label_customers AS STRING) FROM label_checks
UNION ALL SELECT 'churn_rate', CAST(round(churn_rate, 4) AS STRING) FROM label_checks
UNION ALL SELECT 'avg_churn_probability', CAST(round(avg_churn_probability, 4) AS STRING) FROM label_checks
UNION ALL SELECT 'min_churn_probability', CAST(round(min_churn_probability, 4) AS STRING) FROM label_checks
UNION ALL SELECT 'max_churn_probability', CAST(round(max_churn_probability, 4) AS STRING) FROM label_checks
UNION ALL SELECT 'min_observation_date', CAST(min_observation_date AS STRING) FROM feature_checks
UNION ALL SELECT 'max_observation_date', CAST(max_observation_date AS STRING) FROM feature_checks
UNION ALL SELECT 'duplicate_feature_key_count', CAST(duplicate_feature_key_count AS STRING) FROM duplicate_features
UNION ALL SELECT 'duplicate_label_key_count', CAST(duplicate_label_key_count AS STRING) FROM duplicate_labels
UNION ALL SELECT 'orphan_feature_customer_count', CAST(orphan_feature_customer_count AS STRING) FROM orphan_feature_customer
UNION ALL SELECT 'orphan_label_customer_count', CAST(orphan_label_customer_count AS STRING) FROM orphan_label_customer
UNION ALL SELECT 'missing_label_for_feature_count', CAST(missing_label_for_feature_count AS STRING) FROM missing_label_for_feature
UNION ALL SELECT 'missing_feature_for_label_count', CAST(missing_feature_for_label_count AS STRING) FROM missing_feature_for_label
UNION ALL SELECT 'negative_premium_count', CAST(negative_premium_count AS STRING) FROM feature_checks
UNION ALL SELECT 'invalid_email_open_rate_count', CAST(invalid_email_open_rate_count AS STRING) FROM feature_checks
UNION ALL SELECT 'invalid_satisfaction_count', CAST(invalid_satisfaction_count AS STRING) FROM feature_checks
UNION ALL SELECT 'invalid_churn_label_count', CAST(invalid_churn_label_count AS STRING) FROM label_checks
UNION ALL SELECT 'invalid_churn_probability_count', CAST(invalid_churn_probability_count AS STRING) FROM label_checks
ORDER BY metric;

SELECT churn_risk_band, count(*) AS customers, round(avg(churn_label), 4) AS churn_rate, round(avg(churn_probability), 4) AS avg_churn_probability
FROM retainflow.ml.churn_labels
GROUP BY churn_risk_band
ORDER BY avg_churn_probability DESC;

SELECT label_reason, count(*) AS customers, round(avg(churn_label), 4) AS churn_rate, round(avg(churn_probability), 4) AS avg_churn_probability
FROM retainflow.ml.churn_labels
GROUP BY label_reason
ORDER BY customers DESC;

SELECT f.*, l.churn_label, l.churn_probability, l.churn_risk_band, l.label_reason
FROM retainflow.ml.churn_feature_snapshot f
JOIN retainflow.ml.churn_labels l
  ON f.customer_id = l.customer_id
 AND f.observation_date = l.observation_date
ORDER BY l.churn_probability DESC
LIMIT 100;
