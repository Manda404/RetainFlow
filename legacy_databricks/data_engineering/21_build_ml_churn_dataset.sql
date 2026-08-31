-- RetainFlow - Phase 1 ML churn feature snapshot and labels
-- Run after 17_build_gold_customer_360.sql.

DELETE FROM retainflow.ml.churn_labels;
DELETE FROM retainflow.ml.churn_feature_snapshot;

INSERT INTO retainflow.ml.churn_feature_snapshot
SELECT
  g.observation_date,
  g.customer_id,
  g.tenure_months,
  g.active_policy_count,
  g.number_of_products,
  CAST(g.total_annual_premium AS DOUBLE) AS total_annual_premium,
  g.total_claims_12m,
  CAST(g.total_claim_amount_12m AS DOUBLE) AS total_claim_amount_12m,
  g.payment_incidents_6m,
  g.complaints_6m,
  g.interactions_3m,
  g.days_since_last_contact,
  g.digital_sessions_30d,
  g.email_open_rate_6m,
  g.premium_increase_pct_max_12m,
  g.avg_satisfaction_score_12m,
  g.renewal_days_min,
  g.customer_value_score,
  c.customer_segment,
  c.estimated_income_band,
  c.digital_profile,
  c.price_sensitivity_score,
  c.digital_engagement_score,
  c.loyalty_score,
  current_timestamp() AS created_at
FROM retainflow.gold.customer_360_snapshot g
JOIN retainflow.silver.dim_customer c
  ON g.customer_id = c.customer_id;

INSERT INTO retainflow.ml.churn_labels
WITH cfg AS (
  SELECT prediction_horizon_days
  FROM retainflow.monitoring.generation_config
  WHERE is_active = true
),
features AS (
  SELECT
    f.*,
    cfg.prediction_horizon_days,
    rand(1001) AS r_churn
  FROM retainflow.ml.churn_feature_snapshot f
  CROSS JOIN cfg
),
scored AS (
  SELECT
    *,
    (
      -2.15
      + price_sensitivity_score * 1.10
      + premium_increase_pct_max_12m * 2.30
      + least(payment_incidents_6m, 4) * 0.28
      + least(complaints_6m, 4) * 0.34
      + CASE WHEN avg_satisfaction_score_12m < 3.0 THEN 0.60 WHEN avg_satisfaction_score_12m < 3.7 THEN 0.25 ELSE -0.10 END
      + CASE WHEN renewal_days_min BETWEEN 0 AND prediction_horizon_days THEN 0.75 ELSE 0.00 END
      + CASE WHEN days_since_last_contact > 240 THEN 0.32 WHEN days_since_last_contact > 120 THEN 0.14 ELSE -0.05 END
      + CASE WHEN number_of_products <= 1 THEN 0.28 ELSE -0.22 END
      + CASE WHEN customer_segment = 'PRICE_SENSITIVE' THEN 0.30 ELSE 0.00 END
      + CASE WHEN customer_segment = 'LOW_ENGAGEMENT' THEN 0.22 ELSE 0.00 END
      + CASE WHEN customer_segment = 'HIGH_VALUE' THEN -0.10 ELSE 0.00 END
      - loyalty_score * 0.45
      - digital_engagement_score * 0.12
    ) AS churn_logit
  FROM features
),
probabilities AS (
  SELECT
    *,
    1.0 / (1.0 + exp(-churn_logit)) AS churn_probability
  FROM scored
)
SELECT
  observation_date,
  customer_id,
  prediction_horizon_days,
  CASE WHEN r_churn < churn_probability THEN 1 ELSE 0 END AS churn_label,
  churn_probability,
  CASE
    WHEN churn_probability >= 0.55 THEN 'VERY_HIGH'
    WHEN churn_probability >= 0.35 THEN 'HIGH'
    WHEN churn_probability >= 0.18 THEN 'MEDIUM'
    ELSE 'LOW'
  END AS churn_risk_band,
  CASE
    WHEN premium_increase_pct_max_12m >= 0.12 THEN 'PREMIUM_INCREASE'
    WHEN payment_incidents_6m >= 2 THEN 'PAYMENT_INCIDENTS'
    WHEN complaints_6m >= 1 THEN 'SERVICE_COMPLAINTS'
    WHEN avg_satisfaction_score_12m < 3.2 THEN 'LOW_SATISFACTION'
    WHEN renewal_days_min BETWEEN 0 AND prediction_horizon_days THEN 'UPCOMING_RENEWAL'
    WHEN number_of_products <= 1 THEN 'LOW_PRODUCT_DEPTH'
    WHEN days_since_last_contact > 180 THEN 'LOW_ENGAGEMENT'
    ELSE 'BASELINE_RISK'
  END AS label_reason,
  current_timestamp() AS created_at
FROM probabilities;

INSERT INTO retainflow.monitoring.generation_batches
SELECT
  concat('BATCH_ML_CHURN_DATASET_', date_format(current_timestamp(), 'yyyyMMddHHmmss')) AS batch_id,
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
