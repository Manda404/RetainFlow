-- RetainFlow - customer generation checks
-- This version returns compact, easy-to-read validation tables.

WITH customer_checks AS (
  SELECT
    count(*) AS customer_count,
    max(cfg.n_customers) AS configured_n_customers,
    count(CASE WHEN phone IS NULL THEN 1 END) AS missing_phone_count,
    min(floor(months_between(cfg.snapshot_date, birth_date) / 12)) AS min_age,
    percentile_approx(floor(months_between(cfg.snapshot_date, birth_date) / 12), 0.5) AS median_age,
    max(floor(months_between(cfg.snapshot_date, birth_date) / 12)) AS max_age,
    avg(price_sensitivity_score) AS avg_price_sensitivity,
    avg(digital_engagement_score) AS avg_digital_engagement,
    avg(loyalty_score) AS avg_loyalty
  FROM retainflow.silver.dim_customer
  CROSS JOIN (
    SELECT n_customers, snapshot_date
    FROM retainflow.monitoring.generation_config
    WHERE is_active = true
  ) cfg
),
orphan_geography AS (
  SELECT count(*) AS orphan_geography_count
  FROM retainflow.silver.dim_customer c
  LEFT JOIN retainflow.silver.dim_geography g
    ON c.geography_id = g.geography_id
  WHERE g.geography_id IS NULL
),
orphan_acquisition_channel AS (
  SELECT count(*) AS orphan_acquisition_channel_count
  FROM retainflow.silver.dim_customer c
  LEFT JOIN retainflow.silver.dim_channel ch
    ON c.acquisition_channel_id = ch.channel_id
  WHERE ch.channel_id IS NULL
),
orphan_preferred_channel AS (
  SELECT count(*) AS orphan_preferred_channel_count
  FROM retainflow.silver.dim_customer c
  LEFT JOIN retainflow.silver.dim_channel ch
    ON c.preferred_channel_id = ch.channel_id
  WHERE ch.channel_id IS NULL
),
duplicate_customers AS (
  SELECT count(*) AS duplicate_customer_id_count
  FROM (
    SELECT customer_id
    FROM retainflow.silver.dim_customer
    GROUP BY customer_id
    HAVING count(*) > 1
  )
)
SELECT 'customer_count' AS metric, CAST(customer_count AS STRING) AS value FROM customer_checks
UNION ALL SELECT 'configured_n_customers', CAST(configured_n_customers AS STRING) FROM customer_checks
UNION ALL SELECT 'missing_phone_count', CAST(missing_phone_count AS STRING) FROM customer_checks
UNION ALL SELECT 'min_age', CAST(min_age AS STRING) FROM customer_checks
UNION ALL SELECT 'median_age', CAST(median_age AS STRING) FROM customer_checks
UNION ALL SELECT 'max_age', CAST(max_age AS STRING) FROM customer_checks
UNION ALL SELECT 'avg_price_sensitivity', CAST(round(avg_price_sensitivity, 4) AS STRING) FROM customer_checks
UNION ALL SELECT 'avg_digital_engagement', CAST(round(avg_digital_engagement, 4) AS STRING) FROM customer_checks
UNION ALL SELECT 'avg_loyalty', CAST(round(avg_loyalty, 4) AS STRING) FROM customer_checks
UNION ALL SELECT 'orphan_geography_count', CAST(orphan_geography_count AS STRING) FROM orphan_geography
UNION ALL SELECT 'orphan_acquisition_channel_count', CAST(orphan_acquisition_channel_count AS STRING) FROM orphan_acquisition_channel
UNION ALL SELECT 'orphan_preferred_channel_count', CAST(orphan_preferred_channel_count AS STRING) FROM orphan_preferred_channel
UNION ALL SELECT 'duplicate_customer_id_count', CAST(duplicate_customer_id_count AS STRING) FROM duplicate_customers
ORDER BY metric;

SELECT customer_segment, count(*) AS customers
FROM retainflow.silver.dim_customer
GROUP BY customer_segment
ORDER BY customers DESC;

SELECT digital_profile, count(*) AS customers
FROM retainflow.silver.dim_customer
GROUP BY digital_profile
ORDER BY customers DESC;

SELECT estimated_income_band, count(*) AS customers
FROM retainflow.silver.dim_customer
GROUP BY estimated_income_band
ORDER BY customers DESC;
