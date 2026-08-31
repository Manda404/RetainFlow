-- RetainFlow - Phase 1 synthetic policy and policy event generation
-- Run after 03_generate_customers.sql.

DELETE FROM retainflow.silver.fact_policy_events;
DELETE FROM retainflow.silver.fact_policy;

INSERT INTO retainflow.silver.fact_policy
WITH cfg AS (
  SELECT history_start_date, history_end_date, snapshot_date
  FROM retainflow.monitoring.generation_config
  WHERE is_active = true
),
customers AS (
  SELECT
    c.*,
    CAST(floor(months_between(cfg.snapshot_date, c.birth_date) / 12) AS INT) AS age,
    cfg.history_end_date,
    cfg.snapshot_date
  FROM retainflow.silver.dim_customer c
  CROSS JOIN cfg
),
policy_candidates AS (
  SELECT
    c.*,
    policy_seq,
    rand(201) AS r_keep,
    rand(202) AS r_family,
    rand(203) AS r_tier,
    rand(204) AS r_start,
    rand(205) AS r_discount,
    rand(206) AS r_increase,
    rand(207) AS r_cancel,
    rand(208) AS r_cancel_reason
  FROM customers c
  CROSS JOIN (SELECT explode(sequence(1, 4)) AS policy_seq)
),
selected_policies AS (
  SELECT *
  FROM policy_candidates
  WHERE
    policy_seq = 1
    OR (policy_seq = 2 AND r_keep < CASE WHEN household_size >= 3 THEN 0.62 WHEN customer_segment = 'HIGH_VALUE' THEN 0.70 ELSE 0.42 END)
    OR (policy_seq = 3 AND r_keep < CASE WHEN customer_segment = 'HIGH_VALUE' THEN 0.32 WHEN household_size >= 4 THEN 0.26 ELSE 0.14 END)
    OR (policy_seq = 4 AND r_keep < CASE WHEN customer_segment = 'HIGH_VALUE' THEN 0.12 ELSE 0.05 END)
),
policy_choices AS (
  SELECT
    *,
    CASE
      WHEN r_family < 0.30 THEN 'AUTO'
      WHEN r_family < 0.53 THEN 'HOME'
      WHEN r_family < 0.70 THEN 'HEALTH'
      WHEN r_family < 0.81 THEN 'LIFE'
      WHEN r_family < 0.89 THEN 'TRAVEL'
      WHEN r_family < 0.96 THEN 'PET'
      ELSE 'PERSONAL_ACCIDENT'
    END AS product_family,
    CASE
      WHEN estimated_income_band IN ('LOW', 'LOWER_MID') AND r_tier < 0.52 THEN 'BASIC'
      WHEN estimated_income_band IN ('UPPER_MID', 'HIGH') AND r_tier > 0.62 THEN 'PREMIUM'
      WHEN r_tier < 0.33 THEN 'BASIC'
      WHEN r_tier < 0.82 THEN 'STANDARD'
      ELSE 'PREMIUM'
    END AS coverage_tier,
    CASE
      WHEN acquisition_channel_id IN ('CH_WEB', 'CH_MOBILE') THEN acquisition_channel_id
      WHEN preferred_channel_id IN ('CH_CALL_CENTER', 'CH_BRANCH') THEN preferred_channel_id
      ELSE acquisition_channel_id
    END AS sales_channel_id
  FROM selected_policies
),
policy_with_product AS (
  SELECT
    pc.*,
    p.product_id,
    p.base_annual_premium,
    p.default_payment_frequency
  FROM policy_choices pc
  JOIN retainflow.silver.dim_product p
    ON pc.product_family = p.product_family
   AND pc.coverage_tier = p.coverage_tier
),
policy_dates AS (
  SELECT
    *,
    date_add(
      acquisition_date,
      CAST(floor(r_start * greatest(datediff(history_end_date, acquisition_date), 1)) AS INT)
    ) AS policy_start_date
  FROM policy_with_product
),
policy_scored AS (
  SELECT
    *,
    least(0.35, greatest(0.00, 0.03 + r_discount * 0.12 + CASE WHEN customer_segment = 'HIGH_VALUE' THEN 0.06 ELSE 0.00 END)) AS premium_discount_pct,
    least(0.32, greatest(0.00, -0.02 + r_increase * 0.18 + price_sensitivity_score * 0.05)) AS premium_increase_pct_last_renewal,
    (
      0.04
      + price_sensitivity_score * 0.11
      + service_sensitivity_score * 0.05
      + CASE WHEN customer_segment = 'PRICE_SENSITIVE' THEN 0.08 ELSE 0.00 END
      + CASE WHEN customer_segment = 'LOW_ENGAGEMENT' THEN 0.05 ELSE 0.00 END
      - loyalty_score * 0.06
      - CASE WHEN policy_seq >= 3 THEN 0.03 ELSE 0.00 END
    ) AS cancellation_probability
  FROM policy_dates
),
policy_final AS (
  SELECT
    *,
    add_months(policy_start_date, 12) AS first_policy_end_date,
    add_months(policy_start_date, 12 * greatest(1, CAST(ceil(months_between(history_end_date, policy_start_date) / 12) AS INT))) AS computed_policy_end_date,
    r_cancel < cancellation_probability AS is_cancelled
  FROM policy_scored
)
SELECT
  concat('POL_', substr(sha2(concat_ws('|', customer_id, product_id, CAST(policy_seq AS STRING), CAST(policy_start_date AS STRING)), 256), 1, 16)) AS policy_id,
  concat('SRC_POL_', substr(sha2(concat_ws('|', source_customer_id, product_id, CAST(policy_seq AS STRING), CAST(policy_start_date AS STRING)), 256), 1, 16)) AS source_policy_id,
  customer_id,
  product_id,
  sales_channel_id,
  CASE
    WHEN sales_channel_id IN ('CH_WEB', 'CH_MOBILE', 'CH_PARTNER') THEN NULL
    ELSE concat('AGT_', lpad(CAST(1 + pmod(xxhash64(customer_id, sales_channel_id, CAST(policy_seq AS STRING)), 240) AS STRING), 5, '0'))
  END AS agent_id,
  policy_start_date,
  CASE
    WHEN is_cancelled THEN add_months(policy_start_date, 12 * greatest(1, CAST(floor(months_between(history_end_date, policy_start_date) / 12) AS INT)))
    ELSE computed_policy_end_date
  END AS policy_end_date,
  CASE
    WHEN is_cancelled THEN NULL
    ELSE add_months(policy_start_date, 12 * greatest(1, CAST(ceil(months_between(snapshot_date, policy_start_date) / 12) AS INT)))
  END AS next_renewal_date,
  CASE
    WHEN is_cancelled THEN 'CANCELLED'
    WHEN computed_policy_end_date < snapshot_date THEN 'EXPIRED'
    WHEN r_cancel > 0.985 THEN 'LAPSED'
    ELSE 'ACTIVE'
  END AS policy_status,
  default_payment_frequency AS payment_frequency,
  CAST(round(
    base_annual_premium
    * (1.0 + risk_affinity_score * 0.18)
    * (1.0 + CASE WHEN estimated_income_band = 'HIGH' THEN 0.16 WHEN estimated_income_band = 'UPPER_MID' THEN 0.08 ELSE 0.00 END)
    * (1.0 - premium_discount_pct)
    * (1.0 + premium_increase_pct_last_renewal),
    2
  ) AS DECIMAL(12,2)) AS annual_premium,
  premium_discount_pct,
  premium_increase_pct_last_renewal,
  CASE
    WHEN is_cancelled THEN date_sub(
      add_months(policy_start_date, 12 * greatest(1, CAST(floor(months_between(history_end_date, policy_start_date) / 12) AS INT))),
      CAST(floor(r_cancel * 45) AS INT)
    )
    ELSE NULL
  END AS cancellation_date,
  CASE
    WHEN NOT is_cancelled THEN NULL
    WHEN r_cancel_reason < 0.30 THEN 'PRICE_INCREASE'
    WHEN r_cancel_reason < 0.48 THEN 'COMPETITOR_OFFER'
    WHEN r_cancel_reason < 0.64 THEN 'POOR_SERVICE'
    WHEN r_cancel_reason < 0.78 THEN 'PRODUCT_NOT_NEEDED'
    WHEN r_cancel_reason < 0.90 THEN 'PAYMENT_ISSUE'
    ELSE 'UNKNOWN'
  END AS cancellation_reason,
  current_timestamp() AS created_at,
  current_timestamp() AS updated_at
FROM policy_final;

INSERT INTO retainflow.silver.fact_policy_events
WITH policies AS (
  SELECT *
  FROM retainflow.silver.fact_policy
),
subscription_events AS (
  SELECT
    policy_id,
    customer_id,
    product_id,
    policy_start_date AS event_date,
    cast(policy_start_date AS TIMESTAMP) AS event_timestamp,
    'SUBSCRIPTION' AS event_type,
    'NEW_BUSINESS' AS event_reason,
    CAST(NULL AS STRING) AS previous_policy_status,
    'ACTIVE' AS new_policy_status,
    CAST(NULL AS DECIMAL(12,2)) AS previous_annual_premium,
    annual_premium AS new_annual_premium,
    CAST(NULL AS DOUBLE) AS premium_change_pct,
    'POLICY_ADMIN' AS source_system
  FROM policies
),
renewal_events AS (
  SELECT
    p.policy_id,
    p.customer_id,
    p.product_id,
    add_months(p.policy_start_date, renewal_seq * 12) AS event_date,
    cast(add_months(p.policy_start_date, renewal_seq * 12) AS TIMESTAMP) AS event_timestamp,
    'RENEWAL' AS event_type,
    'ANNUAL_RENEWAL' AS event_reason,
    'ACTIVE' AS previous_policy_status,
    'ACTIVE' AS new_policy_status,
    CAST(round(p.annual_premium / (1.0 + p.premium_increase_pct_last_renewal), 2) AS DECIMAL(12,2)) AS previous_annual_premium,
    p.annual_premium AS new_annual_premium,
    p.premium_increase_pct_last_renewal AS premium_change_pct,
    'POLICY_ADMIN' AS source_system
  FROM policies p
  CROSS JOIN (SELECT explode(sequence(1, 5)) AS renewal_seq)
  WHERE add_months(p.policy_start_date, renewal_seq * 12) < coalesce(p.cancellation_date, p.policy_end_date)
),
premium_change_events AS (
  SELECT
    policy_id,
    customer_id,
    product_id,
    date_add(next_renewal_date, -30) AS event_date,
    cast(date_add(next_renewal_date, -30) AS TIMESTAMP) AS event_timestamp,
    'PREMIUM_CHANGE' AS event_type,
    'RENEWAL_PRICING' AS event_reason,
    'ACTIVE' AS previous_policy_status,
    'ACTIVE' AS new_policy_status,
    CAST(round(annual_premium / (1.0 + premium_increase_pct_last_renewal), 2) AS DECIMAL(12,2)) AS previous_annual_premium,
    annual_premium AS new_annual_premium,
    premium_increase_pct_last_renewal AS premium_change_pct,
    'PRICING_ENGINE' AS source_system
  FROM policies
  WHERE next_renewal_date IS NOT NULL
    AND premium_increase_pct_last_renewal >= 0.04
),
cancellation_events AS (
  SELECT
    policy_id,
    customer_id,
    product_id,
    cancellation_date AS event_date,
    cast(cancellation_date AS TIMESTAMP) AS event_timestamp,
    'CANCELLATION' AS event_type,
    cancellation_reason AS event_reason,
    'ACTIVE' AS previous_policy_status,
    'CANCELLED' AS new_policy_status,
    annual_premium AS previous_annual_premium,
    CAST(NULL AS DECIMAL(12,2)) AS new_annual_premium,
    CAST(NULL AS DOUBLE) AS premium_change_pct,
    'POLICY_ADMIN' AS source_system
  FROM policies
  WHERE cancellation_date IS NOT NULL
)
SELECT
  concat('PEVT_', substr(sha2(concat_ws('|', policy_id, event_type, CAST(event_date AS STRING), coalesce(event_reason, 'NA')), 256), 1, 16)) AS policy_event_id,
  policy_id,
  customer_id,
  product_id,
  event_date,
  event_timestamp,
  event_type,
  event_reason,
  previous_policy_status,
  new_policy_status,
  previous_annual_premium,
  new_annual_premium,
  premium_change_pct,
  source_system,
  current_timestamp() AS created_at
FROM (
  SELECT * FROM subscription_events
  UNION ALL SELECT * FROM renewal_events
  UNION ALL SELECT * FROM premium_change_events
  UNION ALL SELECT * FROM cancellation_events
);

INSERT INTO retainflow.monitoring.generation_batches
SELECT
  concat('BATCH_POLICIES_', date_format(current_timestamp(), 'yyyyMMddHHmmss')) AS batch_id,
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
