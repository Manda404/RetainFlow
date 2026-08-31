-- RetainFlow - claim generation checks

WITH claim_checks AS (
  SELECT
    count(*) AS claim_count,
    count(DISTINCT policy_id) AS policies_with_claim,
    avg(claim_amount) AS avg_claim_amount,
    avg(paid_amount) AS avg_paid_amount,
    avg(handling_days) AS avg_handling_days,
    avg(claim_satisfaction_score) AS avg_claim_satisfaction_score,
    min(claim_date) AS min_claim_date,
    max(claim_date) AS max_claim_date,
    count(CASE WHEN claim_amount <= 0 THEN 1 END) AS non_positive_claim_amount_count,
    count(CASE WHEN paid_amount < 0 THEN 1 END) AS negative_paid_amount_count,
    count(CASE WHEN paid_amount > claim_amount THEN 1 END) AS paid_above_claim_amount_count,
    count(CASE WHEN reported_date < claim_date THEN 1 END) AS report_before_claim_count,
    count(CASE WHEN closed_date IS NOT NULL AND closed_date < reported_date THEN 1 END) AS close_before_report_count
  FROM retainflow.silver.fact_claims
),
policy_count AS (
  SELECT count(*) AS policy_count
  FROM retainflow.silver.fact_policy
),
duplicate_claims AS (
  SELECT count(*) AS duplicate_claim_id_count
  FROM (
    SELECT claim_id
    FROM retainflow.silver.fact_claims
    GROUP BY claim_id
    HAVING count(*) > 1
  )
),
orphan_claim_policy AS (
  SELECT count(*) AS orphan_claim_policy_count
  FROM retainflow.silver.fact_claims clm
  LEFT JOIN retainflow.silver.fact_policy p
    ON clm.policy_id = p.policy_id
  WHERE p.policy_id IS NULL
),
orphan_claim_customer AS (
  SELECT count(*) AS orphan_claim_customer_count
  FROM retainflow.silver.fact_claims clm
  LEFT JOIN retainflow.silver.dim_customer c
    ON clm.customer_id = c.customer_id
  WHERE c.customer_id IS NULL
),
orphan_claim_product AS (
  SELECT count(*) AS orphan_claim_product_count
  FROM retainflow.silver.fact_claims clm
  LEFT JOIN retainflow.silver.dim_product p
    ON clm.product_id = p.product_id
  WHERE p.product_id IS NULL
),
claim_outside_policy AS (
  SELECT count(*) AS claim_outside_policy_period_count
  FROM retainflow.silver.fact_claims clm
  JOIN retainflow.silver.fact_policy p
    ON clm.policy_id = p.policy_id
  WHERE clm.claim_date < p.policy_start_date
    OR clm.claim_date > p.policy_end_date
)
SELECT 'policy_count' AS metric, CAST(policy_count AS STRING) AS value FROM policy_count
UNION ALL SELECT 'claim_count', CAST(claim_count AS STRING) FROM claim_checks
UNION ALL SELECT 'policies_with_claim', CAST(policies_with_claim AS STRING) FROM claim_checks
UNION ALL SELECT 'claim_rate_per_policy', CAST(round(claim_count / policy_count, 4) AS STRING) FROM claim_checks CROSS JOIN policy_count
UNION ALL SELECT 'avg_claim_amount', CAST(round(avg_claim_amount, 2) AS STRING) FROM claim_checks
UNION ALL SELECT 'avg_paid_amount', CAST(round(avg_paid_amount, 2) AS STRING) FROM claim_checks
UNION ALL SELECT 'avg_handling_days', CAST(round(avg_handling_days, 2) AS STRING) FROM claim_checks
UNION ALL SELECT 'avg_claim_satisfaction_score', CAST(round(avg_claim_satisfaction_score, 3) AS STRING) FROM claim_checks
UNION ALL SELECT 'min_claim_date', CAST(min_claim_date AS STRING) FROM claim_checks
UNION ALL SELECT 'max_claim_date', CAST(max_claim_date AS STRING) FROM claim_checks
UNION ALL SELECT 'non_positive_claim_amount_count', CAST(non_positive_claim_amount_count AS STRING) FROM claim_checks
UNION ALL SELECT 'negative_paid_amount_count', CAST(negative_paid_amount_count AS STRING) FROM claim_checks
UNION ALL SELECT 'paid_above_claim_amount_count', CAST(paid_above_claim_amount_count AS STRING) FROM claim_checks
UNION ALL SELECT 'report_before_claim_count', CAST(report_before_claim_count AS STRING) FROM claim_checks
UNION ALL SELECT 'close_before_report_count', CAST(close_before_report_count AS STRING) FROM claim_checks
UNION ALL SELECT 'duplicate_claim_id_count', CAST(duplicate_claim_id_count AS STRING) FROM duplicate_claims
UNION ALL SELECT 'orphan_claim_policy_count', CAST(orphan_claim_policy_count AS STRING) FROM orphan_claim_policy
UNION ALL SELECT 'orphan_claim_customer_count', CAST(orphan_claim_customer_count AS STRING) FROM orphan_claim_customer
UNION ALL SELECT 'orphan_claim_product_count', CAST(orphan_claim_product_count AS STRING) FROM orphan_claim_product
UNION ALL SELECT 'claim_outside_policy_period_count', CAST(claim_outside_policy_period_count AS STRING) FROM claim_outside_policy
ORDER BY metric;

SELECT claim_status, count(*) AS claims
FROM retainflow.silver.fact_claims
GROUP BY claim_status
ORDER BY claims DESC;

SELECT claim_type, count(*) AS claims, round(avg(claim_amount), 2) AS avg_claim_amount
FROM retainflow.silver.fact_claims
GROUP BY claim_type
ORDER BY claims DESC;

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
