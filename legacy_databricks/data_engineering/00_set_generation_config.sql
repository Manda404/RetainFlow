-- RetainFlow - active generation configuration
-- Change n_customers here before running generation scripts.
--
-- Recommended values:
--   1000    smoke test
--   10000   local/free edition development
--   100000  larger portfolio once all pipelines are stable

CREATE TABLE IF NOT EXISTS retainflow.monitoring.generation_config (
  config_name STRING COMMENT 'Configuration name. Usually default_dev, smoke_test, or full_dev.',
  is_active BOOLEAN COMMENT 'Only one row should be active for generation scripts.',
  generation_mode STRING COMMENT 'reset or incremental.',
  seed INT COMMENT 'Global deterministic seed.',
  n_customers INT COMMENT 'Number of synthetic customers to generate.',
  history_start_date DATE COMMENT 'Start date of generated business history.',
  history_end_date DATE COMMENT 'End date of generated business history.',
  snapshot_date DATE COMMENT 'Customer 360 observation date.',
  prediction_horizon_days INT COMMENT 'Future churn prediction horizon for later ML steps.',
  max_customer_generation_limit INT COMMENT 'Safety limit used by SQL generators.',
  updated_at TIMESTAMP,
  updated_by STRING
)
USING DELTA
COMMENT 'Active synthetic data generation parameters used by RetainFlow SQL generation scripts.';

DELETE FROM retainflow.monitoring.generation_config;

INSERT INTO retainflow.monitoring.generation_config
SELECT
  'default_dev' AS config_name,
  true AS is_active,
  'reset' AS generation_mode,
  42 AS seed,
  10000 AS n_customers,
  to_date('2021-01-01') AS history_start_date,
  to_date('2025-12-31') AS history_end_date,
  to_date('2025-12-31') AS snapshot_date,
  90 AS prediction_horizon_days,
  1000000 AS max_customer_generation_limit,
  current_timestamp() AS updated_at,
  current_user() AS updated_by;

SELECT *
FROM retainflow.monitoring.generation_config
WHERE is_active = true;
