-- RetainFlow - Phase 1 synthetic customer generation
-- Run after 00_set_generation_config.sql and 02_seed_reference_dimensions.sql.

DELETE FROM retainflow.silver.dim_customer;

INSERT INTO retainflow.silver.dim_customer
WITH active_config AS (
  SELECT
    n_customers,
    history_start_date,
    history_end_date,
    snapshot_date,
    max_customer_generation_limit
  FROM retainflow.monitoring.generation_config
  WHERE is_active = true
),
customer_seed AS (
  SELECT
    CAST(id + 1 AS INT) AS customer_num,
    cfg.history_start_date,
    cfg.history_end_date,
    cfg.snapshot_date,
    rand(101) AS r_age,
    rand(102) AS r_gender,
    rand(103) AS r_geo,
    rand(104) AS r_acquisition,
    rand(105) AS r_channel,
    rand(106) AS r_household,
    rand(107) AS r_employment,
    rand(108) AS r_income,
    rand(109) AS r_digital,
    rand(110) AS r_consent_email,
    rand(111) AS r_consent_sms,
    rand(112) AS r_consent_phone,
    rand(113) AS r_risk,
    rand(114) AS r_price,
    rand(115) AS r_service,
    rand(116) AS r_loyalty,
    rand(117) AS r_claim,
    rand(118) AS r_name
  FROM range(1000000)
  CROSS JOIN active_config cfg
  WHERE id < cfg.n_customers
    AND cfg.n_customers BETWEEN 1 AND cfg.max_customer_generation_limit
),
geography_ranked AS (
  SELECT
    geography_id,
    income_index,
    claim_risk_index,
    digital_adoption_index,
    row_number() OVER (ORDER BY geography_id) AS geography_rank,
    count(*) OVER () AS geography_count
  FROM retainflow.silver.dim_geography
),
customer_geo AS (
  SELECT
    s.*,
    g.geography_id,
    g.income_index,
    g.claim_risk_index,
    g.digital_adoption_index
  FROM customer_seed s
  JOIN geography_ranked g
    ON g.geography_rank = CAST(floor(s.r_geo * g.geography_count) + 1 AS INT)
),
customer_profile AS (
  SELECT
    *,
    CASE
      WHEN r_age < 0.08 THEN CAST(18 + floor(r_age / 0.08 * 7) AS INT)
      WHEN r_age < 0.42 THEN CAST(25 + floor((r_age - 0.08) / 0.34 * 20) AS INT)
      WHEN r_age < 0.78 THEN CAST(45 + floor((r_age - 0.42) / 0.36 * 20) AS INT)
      WHEN r_age < 0.95 THEN CAST(65 + floor((r_age - 0.78) / 0.17 * 15) AS INT)
      ELSE CAST(80 + floor((r_age - 0.95) / 0.05 * 10) AS INT)
    END AS age,
    CASE
      WHEN r_gender < 0.49 THEN 'F'
      WHEN r_gender < 0.98 THEN 'M'
      ELSE 'OTHER'
    END AS gender,
    date_add(
      history_start_date,
      CAST(floor(r_acquisition * datediff(history_end_date, history_start_date)) AS INT)
    ) AS acquisition_date,
    CASE
      WHEN r_channel < 0.25 THEN 'CH_WEB'
      WHEN r_channel < 0.37 THEN 'CH_MOBILE'
      WHEN r_channel < 0.57 THEN 'CH_BRANCH'
      WHEN r_channel < 0.73 THEN 'CH_CALL_CENTER'
      WHEN r_channel < 0.91 THEN 'CH_BROKER'
      ELSE 'CH_PARTNER'
    END AS acquisition_channel_id,
    CASE
      WHEN r_household < 0.22 THEN 1
      WHEN r_household < 0.54 THEN 2
      WHEN r_household < 0.78 THEN 3
      WHEN r_household < 0.93 THEN 4
      ELSE 5
    END AS household_size,
    CASE
      WHEN r_employment < 0.08 THEN 'STUDENT'
      WHEN r_employment < 0.68 THEN 'EMPLOYED'
      WHEN r_employment < 0.80 THEN 'SELF_EMPLOYED'
      WHEN r_employment < 0.91 THEN 'RETIRED'
      ELSE 'UNEMPLOYED'
    END AS employment_status
  FROM customer_geo
),
customer_traits AS (
  SELECT
    *,
    CASE
      WHEN income_index + r_income < 1.12 THEN 'LOW'
      WHEN income_index + r_income < 1.45 THEN 'LOWER_MID'
      WHEN income_index + r_income < 1.78 THEN 'MID'
      WHEN income_index + r_income < 2.08 THEN 'UPPER_MID'
      ELSE 'HIGH'
    END AS estimated_income_band,
    CASE
      WHEN digital_adoption_index + r_digital + CASE WHEN age < 35 THEN 0.35 WHEN age > 65 THEN -0.25 ELSE 0.00 END < 1.05 THEN 'LOW'
      WHEN digital_adoption_index + r_digital + CASE WHEN age < 35 THEN 0.35 WHEN age > 65 THEN -0.25 ELSE 0.00 END < 1.65 THEN 'MEDIUM'
      ELSE 'HIGH'
    END AS digital_profile,
    least(1.0, greatest(0.0, 0.25 + r_risk * 0.55 + (claim_risk_index - 1.0) * 0.25)) AS risk_affinity_score,
    least(1.0, greatest(0.0, 0.25 + r_price * 0.55 + CASE WHEN income_index < 0.95 THEN 0.15 ELSE -0.05 END)) AS price_sensitivity_score,
    least(1.0, greatest(0.0, 0.20 + r_service * 0.65 + CASE WHEN age > 60 THEN 0.08 ELSE 0.00 END)) AS service_sensitivity_score,
    least(1.0, greatest(0.0, 0.18 + r_digital * 0.60 + (digital_adoption_index - 1.0) * 0.30 + CASE WHEN age < 35 THEN 0.12 WHEN age > 65 THEN -0.12 ELSE 0.00 END)) AS digital_engagement_score,
    least(1.0, greatest(0.0, 0.30 + r_loyalty * 0.55 + CASE WHEN age > 45 THEN 0.10 ELSE 0.00 END)) AS loyalty_score,
    least(1.0, greatest(0.0, 0.18 + r_claim * 0.55 + (claim_risk_index - 1.0) * 0.35)) AS claim_propensity_score
  FROM customer_profile
),
customer_segmented AS (
  SELECT
    *,
    CASE
      WHEN price_sensitivity_score >= 0.70 THEN 'PRICE_SENSITIVE'
      WHEN digital_engagement_score >= 0.70 THEN 'DIGITAL_FIRST'
      WHEN household_size >= 3 AND age BETWEEN 30 AND 58 THEN 'FAMILY_PROTECTOR'
      WHEN estimated_income_band IN ('UPPER_MID', 'HIGH') AND loyalty_score >= 0.55 THEN 'HIGH_VALUE'
      ELSE 'LOW_ENGAGEMENT'
    END AS customer_segment,
    CASE
      WHEN digital_profile = 'HIGH' THEN 'CH_MOBILE'
      WHEN digital_profile = 'MEDIUM' THEN 'CH_EMAIL'
      WHEN age > 65 THEN 'CH_CALL_CENTER'
      ELSE acquisition_channel_id
    END AS preferred_channel_id
  FROM customer_traits
),
customer_named AS (
  SELECT
    *,
    element_at(array('Emma', 'Louise', 'Jade', 'Alice', 'Chloe', 'Sofia', 'Ines', 'Lea', 'Manon', 'Camille'), CAST(pmod(customer_num, 10) + 1 AS INT)) AS female_first_name,
    element_at(array('Lucas', 'Hugo', 'Gabriel', 'Louis', 'Nathan', 'Noah', 'Adam', 'Jules', 'Leo', 'Arthur'), CAST(pmod(customer_num, 10) + 1 AS INT)) AS male_first_name,
    element_at(array('Martin', 'Bernard', 'Dubois', 'Thomas', 'Robert', 'Richard', 'Petit', 'Durand', 'Leroy', 'Moreau', 'Simon', 'Laurent'), CAST(pmod(customer_num, 12) + 1 AS INT)) AS last_name
  FROM customer_segmented
)
SELECT
  concat('CUST_', lpad(CAST(customer_num AS STRING), 8, '0')) AS customer_id,
  concat('SRC_CUST_', lpad(CAST(customer_num AS STRING), 8, '0')) AS source_customer_id,
  CASE WHEN gender = 'F' THEN female_first_name WHEN gender = 'M' THEN male_first_name ELSE 'Alex' END AS first_name,
  last_name,
  add_months(snapshot_date, -age * 12 - CAST(floor(r_name * 12) AS INT)) AS birth_date,
  gender,
  lower(concat(
    CASE WHEN gender = 'F' THEN female_first_name WHEN gender = 'M' THEN male_first_name ELSE 'Alex' END,
    '.',
    last_name,
    '.',
    CAST(customer_num AS STRING),
    '@example.retainflow'
  )) AS email,
  CASE
    WHEN pmod(customer_num, 31) = 0 THEN NULL
    ELSE concat('+33', CAST(600000000 + customer_num AS STRING))
  END AS phone,
  geography_id,
  acquisition_date,
  acquisition_channel_id,
  preferred_channel_id,
  employment_status,
  household_size,
  estimated_income_band,
  digital_profile,
  r_consent_email < CASE WHEN digital_profile = 'HIGH' THEN 0.92 WHEN digital_profile = 'MEDIUM' THEN 0.78 ELSE 0.55 END AS consent_email,
  r_consent_sms < CASE WHEN digital_profile = 'HIGH' THEN 0.70 WHEN digital_profile = 'MEDIUM' THEN 0.52 ELSE 0.32 END AS consent_sms,
  r_consent_phone < CASE WHEN preferred_channel_id IN ('CH_CALL_CENTER', 'CH_BRANCH') THEN 0.86 ELSE 0.64 END AS consent_phone,
  customer_segment,
  risk_affinity_score,
  price_sensitivity_score,
  service_sensitivity_score,
  digital_engagement_score,
  loyalty_score,
  claim_propensity_score,
  current_timestamp() AS created_at,
  current_timestamp() AS updated_at
FROM customer_named;

INSERT INTO retainflow.monitoring.generation_batches
SELECT
  concat('BATCH_CUSTOMERS_', date_format(current_timestamp(), 'yyyyMMddHHmmss')) AS batch_id,
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
