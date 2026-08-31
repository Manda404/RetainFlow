-- RetainFlow - Phase 1 synthetic claim generation
-- Run after 05_generate_policies.sql.

DELETE FROM retainflow.silver.fact_claims;

INSERT INTO retainflow.silver.fact_claims
WITH cfg AS (
  SELECT snapshot_date
  FROM retainflow.monitoring.generation_config
  WHERE is_active = true
),
policy_base AS (
  SELECT
    p.policy_id,
    p.customer_id,
    p.product_id,
    p.policy_start_date,
    least(p.policy_end_date, cfg.snapshot_date) AS claim_end_date,
    p.annual_premium,
    pr.product_family,
    pr.risk_level,
    pr.deductible_amount,
    c.claim_propensity_score,
    c.risk_affinity_score,
    c.service_sensitivity_score,
    g.claim_risk_index,
    CASE
      WHEN pr.product_family = 'AUTO' THEN 0.11
      WHEN pr.product_family = 'HOME' THEN 0.07
      WHEN pr.product_family = 'HEALTH' THEN 0.18
      WHEN pr.product_family = 'LIFE' THEN 0.02
      WHEN pr.product_family = 'TRAVEL' THEN 0.05
      WHEN pr.product_family = 'PET' THEN 0.14
      ELSE 0.04
    END AS annual_claim_frequency
  FROM retainflow.silver.fact_policy p
  JOIN retainflow.silver.dim_product pr
    ON p.product_id = pr.product_id
  JOIN retainflow.silver.dim_customer c
    ON p.customer_id = c.customer_id
  JOIN retainflow.silver.dim_geography g
    ON c.geography_id = g.geography_id
  CROSS JOIN cfg
),
claim_candidates AS (
  SELECT
    *,
    claim_seq,
    rand(401) AS r_keep,
    rand(402) AS r_date,
    rand(403) AS r_amount,
    rand(404) AS r_status,
    rand(405) AS r_report_delay,
    rand(406) AS r_handling,
    rand(407) AS r_fraud,
    rand(408) AS r_type
  FROM policy_base
  CROSS JOIN (SELECT explode(sequence(1, 4)) AS claim_seq)
),
claim_scored AS (
  SELECT
    *,
    greatest(datediff(claim_end_date, policy_start_date), 1) AS covered_days,
    least(
      0.75,
      annual_claim_frequency
      * greatest(datediff(claim_end_date, policy_start_date), 1) / 365.0
      * (0.65 + claim_propensity_score)
      * claim_risk_index
      * CASE WHEN claim_seq = 1 THEN 1.00 WHEN claim_seq = 2 THEN 0.35 WHEN claim_seq = 3 THEN 0.12 ELSE 0.04 END
    ) AS claim_probability
  FROM claim_candidates
),
selected_claims AS (
  SELECT
    *,
    date_add(policy_start_date, CAST(floor(r_date * covered_days) AS INT)) AS claim_date
  FROM claim_scored
  WHERE r_keep < claim_probability
),
claim_typed AS (
  SELECT
    *,
    CASE
      WHEN product_family = 'AUTO' AND r_type < 0.42 THEN 'COLLISION'
      WHEN product_family = 'AUTO' AND r_type < 0.72 THEN 'GLASS_DAMAGE'
      WHEN product_family = 'AUTO' THEN 'THEFT_OR_VANDALISM'
      WHEN product_family = 'HOME' AND r_type < 0.38 THEN 'WATER_DAMAGE'
      WHEN product_family = 'HOME' AND r_type < 0.68 THEN 'FIRE_OR_SMOKE'
      WHEN product_family = 'HOME' THEN 'BURGLARY'
      WHEN product_family = 'HEALTH' AND r_type < 0.45 THEN 'MEDICAL_EXPENSE'
      WHEN product_family = 'HEALTH' AND r_type < 0.78 THEN 'HOSPITALIZATION'
      WHEN product_family = 'HEALTH' THEN 'DENTAL_OR_OPTICAL'
      WHEN product_family = 'LIFE' THEN 'LIFE_EVENT'
      WHEN product_family = 'TRAVEL' AND r_type < 0.50 THEN 'TRIP_CANCELLATION'
      WHEN product_family = 'TRAVEL' THEN 'BAGGAGE_OR_DELAY'
      WHEN product_family = 'PET' AND r_type < 0.60 THEN 'VETERINARY_CARE'
      WHEN product_family = 'PET' THEN 'ACCIDENT_OR_SURGERY'
      ELSE 'PERSONAL_INJURY'
    END AS claim_type,
    CASE
      WHEN product_family = 'AUTO' THEN 950.0
      WHEN product_family = 'HOME' THEN 1300.0
      WHEN product_family = 'HEALTH' THEN 620.0
      WHEN product_family = 'LIFE' THEN 8500.0
      WHEN product_family = 'TRAVEL' THEN 430.0
      WHEN product_family = 'PET' THEN 360.0
      ELSE 700.0
    END AS base_claim_amount
  FROM selected_claims
),
claim_final AS (
  SELECT
    *,
    CAST(round(base_claim_amount * (0.25 + r_amount * r_amount * 5.5) * (0.75 + risk_affinity_score), 2) AS DECIMAL(14,2)) AS claim_amount,
    CAST(1 + floor(r_report_delay * 12) AS INT) AS report_delay_days,
    CAST(
      3
      + floor(r_handling * 35)
      + CASE WHEN r_amount > 0.88 THEN 20 ELSE 0 END
      + CASE WHEN r_fraud > 0.975 THEN 30 ELSE 0 END
      AS INT
    ) AS handling_days,
    r_fraud > 0.975 AS fraud_suspicion_flag
  FROM claim_typed
)
SELECT
  concat('CLM_', substr(sha2(concat_ws('|', policy_id, CAST(claim_seq AS STRING), CAST(claim_date AS STRING)), 256), 1, 16)) AS claim_id,
  concat('SRC_CLM_', substr(sha2(concat_ws('|', policy_id, CAST(claim_seq AS STRING), CAST(claim_date AS STRING)), 256), 1, 16)) AS source_claim_id,
  policy_id,
  customer_id,
  product_id,
  claim_date,
  date_add(claim_date, report_delay_days) AS reported_date,
  CASE
    WHEN r_status < 0.08 THEN NULL
    ELSE date_add(date_add(claim_date, report_delay_days), handling_days)
  END AS closed_date,
  claim_type,
  CASE
    WHEN r_status < 0.04 THEN 'OPEN'
    WHEN r_status < 0.08 THEN 'UNDER_REVIEW'
    WHEN fraud_suspicion_flag OR r_status < 0.17 THEN 'REJECTED'
    WHEN r_status < 0.88 THEN 'CLOSED'
    ELSE 'APPROVED'
  END AS claim_status,
  claim_amount,
  CASE
    WHEN fraud_suspicion_flag OR r_status < 0.17 THEN CAST(0.00 AS DECIMAL(14,2))
    ELSE CAST(greatest(0.00, round(CAST(claim_amount AS DOUBLE) - CAST(deductible_amount AS DOUBLE), 2)) AS DECIMAL(14,2))
  END AS paid_amount,
  deductible_amount,
  handling_days,
  fraud_suspicion_flag,
  least(
    5.0,
    greatest(
      1.0,
      4.7
      - CASE WHEN fraud_suspicion_flag OR r_status < 0.17 THEN 1.8 ELSE 0.0 END
      - CASE WHEN handling_days > 35 THEN 0.8 WHEN handling_days > 20 THEN 0.35 ELSE 0.0 END
      - service_sensitivity_score * 0.35
      + rand(409) * 0.45
    )
  ) AS claim_satisfaction_score,
  current_timestamp() AS created_at,
  current_timestamp() AS updated_at
FROM claim_final;

INSERT INTO retainflow.monitoring.generation_batches
SELECT
  concat('BATCH_CLAIMS_', date_format(current_timestamp(), 'yyyyMMddHHmmss')) AS batch_id,
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
