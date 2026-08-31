-- RetainFlow - payment generation checks

WITH payment_checks AS (
  SELECT
    count(*) AS payment_count,
    count(DISTINCT policy_id) AS policies_with_payment,
    avg(payment_amount) AS avg_payment_amount,
    min(due_date) AS min_due_date,
    max(due_date) AS max_due_date,
    count(CASE WHEN payment_amount <= 0 THEN 1 END) AS non_positive_payment_amount_count,
    count(CASE WHEN payment_status = 'LATE' AND (days_late IS NULL OR days_late <= 0) THEN 1 END) AS invalid_late_payment_count,
    count(CASE WHEN payment_status IN ('PAID', 'REFUNDED') AND payment_date IS NULL THEN 1 END) AS missing_paid_date_count,
    count(CASE WHEN payment_status IN ('REJECTED', 'WRITTEN_OFF') AND rejection_reason IS NULL THEN 1 END) AS missing_rejection_reason_count
  FROM retainflow.silver.fact_payments
),
policy_count AS (
  SELECT count(*) AS policy_count
  FROM retainflow.silver.fact_policy
),
duplicate_payments AS (
  SELECT count(*) AS duplicate_payment_id_count
  FROM (
    SELECT payment_id
    FROM retainflow.silver.fact_payments
    GROUP BY payment_id
    HAVING count(*) > 1
  )
),
orphan_payment_policy AS (
  SELECT count(*) AS orphan_payment_policy_count
  FROM retainflow.silver.fact_payments pay
  LEFT JOIN retainflow.silver.fact_policy p
    ON pay.policy_id = p.policy_id
  WHERE p.policy_id IS NULL
),
orphan_payment_customer AS (
  SELECT count(*) AS orphan_payment_customer_count
  FROM retainflow.silver.fact_payments pay
  LEFT JOIN retainflow.silver.dim_customer c
    ON pay.customer_id = c.customer_id
  WHERE c.customer_id IS NULL
),
payment_outside_policy AS (
  SELECT count(*) AS payment_outside_policy_period_count
  FROM retainflow.silver.fact_payments pay
  JOIN retainflow.silver.fact_policy p
    ON pay.policy_id = p.policy_id
  WHERE pay.due_date < p.policy_start_date
    OR pay.due_date > p.policy_end_date
)
SELECT 'policy_count' AS metric, CAST(policy_count AS STRING) AS value FROM policy_count
UNION ALL SELECT 'payment_count', CAST(payment_count AS STRING) FROM payment_checks
UNION ALL SELECT 'policies_with_payment', CAST(policies_with_payment AS STRING) FROM payment_checks
UNION ALL SELECT 'avg_payments_per_policy', CAST(round(payment_count / policy_count, 4) AS STRING) FROM payment_checks CROSS JOIN policy_count
UNION ALL SELECT 'avg_payment_amount', CAST(round(avg_payment_amount, 2) AS STRING) FROM payment_checks
UNION ALL SELECT 'min_due_date', CAST(min_due_date AS STRING) FROM payment_checks
UNION ALL SELECT 'max_due_date', CAST(max_due_date AS STRING) FROM payment_checks
UNION ALL SELECT 'non_positive_payment_amount_count', CAST(non_positive_payment_amount_count AS STRING) FROM payment_checks
UNION ALL SELECT 'invalid_late_payment_count', CAST(invalid_late_payment_count AS STRING) FROM payment_checks
UNION ALL SELECT 'missing_paid_date_count', CAST(missing_paid_date_count AS STRING) FROM payment_checks
UNION ALL SELECT 'missing_rejection_reason_count', CAST(missing_rejection_reason_count AS STRING) FROM payment_checks
UNION ALL SELECT 'duplicate_payment_id_count', CAST(duplicate_payment_id_count AS STRING) FROM duplicate_payments
UNION ALL SELECT 'orphan_payment_policy_count', CAST(orphan_payment_policy_count AS STRING) FROM orphan_payment_policy
UNION ALL SELECT 'orphan_payment_customer_count', CAST(orphan_payment_customer_count AS STRING) FROM orphan_payment_customer
UNION ALL SELECT 'payment_outside_policy_period_count', CAST(payment_outside_policy_period_count AS STRING) FROM payment_outside_policy
ORDER BY metric;

SELECT payment_status, count(*) AS payments
FROM retainflow.silver.fact_payments
GROUP BY payment_status
ORDER BY payments DESC;

SELECT payment_method, count(*) AS payments
FROM retainflow.silver.fact_payments
GROUP BY payment_method
ORDER BY payments DESC;

SELECT payment_year, count(*) AS payments
FROM retainflow.silver.fact_payments
GROUP BY payment_year
ORDER BY payment_year;
