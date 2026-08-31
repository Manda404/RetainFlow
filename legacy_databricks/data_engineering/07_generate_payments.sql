-- RetainFlow - Phase 1 synthetic payment generation
-- Run after 05_generate_policies.sql.

DELETE FROM retainflow.silver.fact_payments;

INSERT INTO retainflow.silver.fact_payments
WITH cfg AS (
  SELECT snapshot_date
  FROM retainflow.monitoring.generation_config
  WHERE is_active = true
),
policy_base AS (
  SELECT
    p.policy_id,
    p.customer_id,
    p.policy_start_date,
    least(p.policy_end_date, cfg.snapshot_date) AS payment_end_date,
    p.payment_frequency,
    p.annual_premium,
    p.policy_status,
    c.estimated_income_band,
    c.price_sensitivity_score,
    c.loyalty_score,
    CASE
      WHEN p.payment_frequency = 'MONTHLY' THEN 1
      WHEN p.payment_frequency = 'QUARTERLY' THEN 3
      ELSE 12
    END AS payment_step_months,
    CASE
      WHEN p.payment_frequency = 'MONTHLY' THEN 12
      WHEN p.payment_frequency = 'QUARTERLY' THEN 4
      ELSE 1
    END AS payments_per_year
  FROM retainflow.silver.fact_policy p
  JOIN retainflow.silver.dim_customer c
    ON p.customer_id = c.customer_id
  CROSS JOIN cfg
),
payment_schedule AS (
  SELECT
    *,
    installment_seq,
    add_months(policy_start_date, installment_seq * payment_step_months) AS due_date,
    rand(301) AS r_status,
    rand(302) AS r_late_days,
    rand(303) AS r_method,
    rand(304) AS r_rejection_reason
  FROM policy_base
  CROSS JOIN (SELECT explode(sequence(0, 72)) AS installment_seq)
  WHERE add_months(policy_start_date, installment_seq * payment_step_months) <= payment_end_date
),
payment_scored AS (
  SELECT
    *,
    least(
      0.18,
      greatest(
        0.01,
        0.018
        + CASE WHEN estimated_income_band = 'LOW' THEN 0.045 WHEN estimated_income_band = 'LOWER_MID' THEN 0.025 ELSE 0.005 END
        + price_sensitivity_score * 0.035
        - loyalty_score * 0.015
      )
    ) AS rejection_probability,
    least(
      0.26,
      greatest(
        0.02,
        0.045
        + CASE WHEN estimated_income_band IN ('LOW', 'LOWER_MID') THEN 0.045 ELSE 0.010 END
        + price_sensitivity_score * 0.040
        - loyalty_score * 0.020
      )
    ) AS late_probability
  FROM payment_schedule
),
payment_final AS (
  SELECT
    *,
    CASE
      WHEN r_status < rejection_probability * 0.10 THEN 'WRITTEN_OFF'
      WHEN r_status < rejection_probability THEN 'REJECTED'
      WHEN r_status < rejection_probability + late_probability THEN 'LATE'
      WHEN policy_status = 'CANCELLED' AND r_status > 0.992 THEN 'REFUNDED'
      ELSE 'PAID'
    END AS payment_status,
    CASE
      WHEN r_late_days < 0.60 THEN CAST(1 + floor(r_late_days * 10) AS INT)
      WHEN r_late_days < 0.90 THEN CAST(10 + floor(r_late_days * 22) AS INT)
      ELSE CAST(30 + floor(r_late_days * 45) AS INT)
    END AS generated_days_late
  FROM payment_scored
)
SELECT
  concat('PAY_', substr(sha2(concat_ws('|', policy_id, CAST(due_date AS STRING)), 256), 1, 16)) AS payment_id,
  policy_id,
  customer_id,
  due_date,
  CASE
    WHEN payment_status IN ('REJECTED', 'WRITTEN_OFF') THEN NULL
    WHEN payment_status = 'LATE' THEN date_add(due_date, generated_days_late)
    WHEN payment_status = 'REFUNDED' THEN date_add(due_date, CAST(floor(r_late_days * 20) AS INT))
    ELSE date_add(due_date, CAST(floor(r_late_days * 3) AS INT))
  END AS payment_date,
  year(due_date) AS payment_year,
  CAST(round(annual_premium / payments_per_year, 2) AS DECIMAL(12,2)) AS payment_amount,
  payment_status,
  CASE
    WHEN r_method < 0.55 THEN 'DIRECT_DEBIT'
    WHEN r_method < 0.78 THEN 'CARD'
    WHEN r_method < 0.91 THEN 'BANK_TRANSFER'
    WHEN r_method < 0.97 THEN 'CHECK'
    WHEN r_method < 0.99 THEN 'WALLET'
    ELSE 'CASH'
  END AS payment_method,
  CASE
    WHEN payment_status = 'LATE' THEN generated_days_late
    WHEN payment_status IN ('REJECTED', 'WRITTEN_OFF') THEN NULL
    ELSE 0
  END AS days_late,
  CASE
    WHEN payment_status NOT IN ('REJECTED', 'WRITTEN_OFF') THEN NULL
    WHEN r_rejection_reason < 0.35 THEN 'INSUFFICIENT_FUNDS'
    WHEN r_rejection_reason < 0.58 THEN 'EXPIRED_CARD'
    WHEN r_rejection_reason < 0.76 THEN 'DIRECT_DEBIT_REJECTED'
    WHEN r_rejection_reason < 0.90 THEN 'ACCOUNT_CLOSED'
    ELSE 'TECHNICAL_ERROR'
  END AS rejection_reason,
  current_timestamp() AS created_at,
  current_timestamp() AS updated_at
FROM payment_final;

INSERT INTO retainflow.monitoring.generation_batches
SELECT
  concat('BATCH_PAYMENTS_', date_format(current_timestamp(), 'yyyyMMddHHmmss')) AS batch_id,
  current_timestamp() AS run_started_at,
  current_timestamp() AS run_finished_at,
  cfg.generation_mode,
  cfg.seed,
  cfg.n_customers,
  cfg.history_start_date,
  cfg.history_end_date,
  'SUCCEEDED' AS status,
  NULL AS error_message,
  current_user() AS created_by
FROM retainflow.monitoring.generation_config cfg
WHERE cfg.is_active = true;
