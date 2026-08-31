-- RetainFlow - Gold customer 360 checks

WITH gold_checks AS (
  SELECT
    count(*) AS customer_360_count,
    count(DISTINCT customer_id) AS distinct_customers,
    min(observation_date) AS min_observation_date,
    max(observation_date) AS max_observation_date,
    avg(customer_value_score) AS avg_customer_value_score,
    count(CASE WHEN tenure_months < 0 THEN 1 END) AS negative_tenure_count,
    count(CASE WHEN active_policy_count < 0 THEN 1 END) AS negative_active_policy_count,
    count(CASE WHEN total_annual_premium < 0 THEN 1 END) AS negative_total_annual_premium_count,
    count(CASE WHEN total_claims_12m < 0 THEN 1 END) AS negative_claim_count,
    count(CASE WHEN payment_incidents_6m < 0 THEN 1 END) AS negative_payment_incident_count,
    count(CASE WHEN complaints_6m < 0 THEN 1 END) AS negative_complaint_count,
    count(CASE WHEN email_open_rate_6m < 0 OR email_open_rate_6m > 1 THEN 1 END) AS invalid_email_open_rate_count,
    count(CASE WHEN avg_satisfaction_score_12m < 1 OR avg_satisfaction_score_12m > 5 THEN 1 END) AS invalid_satisfaction_score_count,
    count(CASE WHEN latent_churn_risk_band NOT IN ('LOW', 'MEDIUM', 'HIGH', 'VERY_HIGH') THEN 1 END) AS invalid_churn_risk_band_count
  FROM retainflow.gold.customer_360_snapshot
),
customer_count AS (
  SELECT count(*) AS customer_count
  FROM retainflow.silver.dim_customer
),
duplicate_customer_360 AS (
  SELECT count(*) AS duplicate_customer_360_count
  FROM (
    SELECT observation_date, customer_id
    FROM retainflow.gold.customer_360_snapshot
    GROUP BY observation_date, customer_id
    HAVING count(*) > 1
  )
),
orphan_customer_360 AS (
  SELECT count(*) AS orphan_customer_360_count
  FROM retainflow.gold.customer_360_snapshot g
  LEFT JOIN retainflow.silver.dim_customer c
    ON g.customer_id = c.customer_id
  WHERE c.customer_id IS NULL
)
SELECT 'customer_count' AS metric, CAST(customer_count AS STRING) AS value FROM customer_count
UNION ALL SELECT 'customer_360_count', CAST(customer_360_count AS STRING) FROM gold_checks
UNION ALL SELECT 'distinct_customers', CAST(distinct_customers AS STRING) FROM gold_checks
UNION ALL SELECT 'coverage_rate', CAST(round(customer_360_count / customer_count, 4) AS STRING) FROM gold_checks CROSS JOIN customer_count
UNION ALL SELECT 'min_observation_date', CAST(min_observation_date AS STRING) FROM gold_checks
UNION ALL SELECT 'max_observation_date', CAST(max_observation_date AS STRING) FROM gold_checks
UNION ALL SELECT 'avg_customer_value_score', CAST(round(avg_customer_value_score, 3) AS STRING) FROM gold_checks
UNION ALL SELECT 'duplicate_customer_360_count', CAST(duplicate_customer_360_count AS STRING) FROM duplicate_customer_360
UNION ALL SELECT 'orphan_customer_360_count', CAST(orphan_customer_360_count AS STRING) FROM orphan_customer_360
UNION ALL SELECT 'negative_tenure_count', CAST(negative_tenure_count AS STRING) FROM gold_checks
UNION ALL SELECT 'negative_active_policy_count', CAST(negative_active_policy_count AS STRING) FROM gold_checks
UNION ALL SELECT 'negative_total_annual_premium_count', CAST(negative_total_annual_premium_count AS STRING) FROM gold_checks
UNION ALL SELECT 'negative_claim_count', CAST(negative_claim_count AS STRING) FROM gold_checks
UNION ALL SELECT 'negative_payment_incident_count', CAST(negative_payment_incident_count AS STRING) FROM gold_checks
UNION ALL SELECT 'negative_complaint_count', CAST(negative_complaint_count AS STRING) FROM gold_checks
UNION ALL SELECT 'invalid_email_open_rate_count', CAST(invalid_email_open_rate_count AS STRING) FROM gold_checks
UNION ALL SELECT 'invalid_satisfaction_score_count', CAST(invalid_satisfaction_score_count AS STRING) FROM gold_checks
UNION ALL SELECT 'invalid_churn_risk_band_count', CAST(invalid_churn_risk_band_count AS STRING) FROM gold_checks
ORDER BY metric;

SELECT latent_churn_risk_band, count(*) AS customers, round(avg(customer_value_score), 3) AS avg_customer_value_score
FROM retainflow.gold.customer_360_snapshot
GROUP BY latent_churn_risk_band
ORDER BY customers DESC;

SELECT
  active_policy_count,
  count(*) AS customers,
  round(avg(total_annual_premium), 2) AS avg_total_annual_premium,
  round(avg(payment_incidents_6m), 3) AS avg_payment_incidents_6m,
  round(avg(complaints_6m), 3) AS avg_complaints_6m
FROM retainflow.gold.customer_360_snapshot
GROUP BY active_policy_count
ORDER BY active_policy_count;

SELECT *
FROM retainflow.gold.customer_360_snapshot
ORDER BY customer_value_score DESC, payment_incidents_6m DESC
LIMIT 100;
