-- RetainFlow - Phase 1 synthetic retention action generation
-- Run after 13_generate_marketing_quotes.sql.

DELETE FROM retainflow.silver.fact_retention_actions;

INSERT INTO retainflow.silver.fact_retention_actions
WITH cfg AS (
  SELECT history_start_date, history_end_date, snapshot_date
  FROM retainflow.monitoring.generation_config
  WHERE is_active = true
),
policy_signals AS (
  SELECT
    p.policy_id,
    p.customer_id,
    p.next_renewal_date,
    p.annual_premium,
    p.premium_increase_pct_last_renewal,
    p.policy_status,
    c.customer_segment,
    c.preferred_channel_id,
    c.price_sensitivity_score,
    c.service_sensitivity_score,
    c.digital_engagement_score,
    c.loyalty_score,
    cfg.history_start_date,
    cfg.history_end_date,
    cfg.snapshot_date,
    count(DISTINCT CASE WHEN pay.payment_status IN ('LATE', 'REJECTED', 'WRITTEN_OFF') THEN pay.payment_id END) AS payment_incidents,
    count(DISTINCT CASE WHEN cs.case_type IN ('COMPLAINT', 'CANCELLATION_INTENT') THEN cs.case_id END) AS complaint_cases,
    count(DISTINCT CASE WHEN clm.claim_status = 'REJECTED' OR clm.claim_satisfaction_score < 3.0 THEN clm.claim_id END) AS bad_claim_experiences,
    count(DISTINCT CASE WHEN cc.campaign_type = 'RETENTION' AND cc.responded_flag THEN cc.campaign_contact_id END) AS retention_campaign_responses,
    count(DISTINCT q.quote_id) AS quote_count
  FROM retainflow.silver.fact_policy p
  JOIN retainflow.silver.dim_customer c
    ON p.customer_id = c.customer_id
  CROSS JOIN cfg
  LEFT JOIN retainflow.silver.fact_payments pay
    ON p.policy_id = pay.policy_id
  LEFT JOIN retainflow.silver.fact_customer_service cs
    ON p.policy_id = cs.policy_id
  LEFT JOIN retainflow.silver.fact_claims clm
    ON p.policy_id = clm.policy_id
  LEFT JOIN retainflow.silver.fact_campaign_contact cc
    ON p.customer_id = cc.customer_id
  LEFT JOIN retainflow.silver.fact_quotes q
    ON p.customer_id = q.customer_id
  WHERE p.policy_status IN ('ACTIVE', 'LAPSED')
  GROUP BY
    p.policy_id,
    p.customer_id,
    p.next_renewal_date,
    p.annual_premium,
    p.premium_increase_pct_last_renewal,
    p.policy_status,
    c.customer_segment,
    c.preferred_channel_id,
    c.price_sensitivity_score,
    c.service_sensitivity_score,
    c.digital_engagement_score,
    c.loyalty_score,
    cfg.history_start_date,
    cfg.history_end_date,
    cfg.snapshot_date
),
retention_scored AS (
  SELECT
    *,
    (
      0.08
      + premium_increase_pct_last_renewal * 1.25
      + least(payment_incidents, 3) * 0.07
      + least(complaint_cases, 3) * 0.10
      + least(bad_claim_experiences, 2) * 0.12
      + CASE WHEN customer_segment = 'HIGH_VALUE' THEN 0.16 ELSE 0.00 END
      + CASE WHEN customer_segment = 'PRICE_SENSITIVE' THEN 0.12 ELSE 0.00 END
      + CASE WHEN customer_segment = 'LOW_ENGAGEMENT' THEN 0.08 ELSE 0.00 END
      + CASE WHEN next_renewal_date IS NOT NULL AND datediff(next_renewal_date, snapshot_date) BETWEEN 0 AND 120 THEN 0.18 ELSE 0.00 END
      - loyalty_score * 0.05
    ) AS retention_action_probability,
    rand(901) AS r_keep,
    rand(902) AS r_date,
    rand(903) AS r_accept,
    rand(904) AS r_retained,
    rand(905) AS r_agent,
    rand(906) AS r_value
  FROM policy_signals
),
selected_actions AS (
  SELECT *
  FROM retention_scored
  WHERE r_keep < least(0.82, retention_action_probability)
),
action_typed AS (
  SELECT
    *,
    CASE
      WHEN premium_increase_pct_last_renewal >= 0.10 AND price_sensitivity_score >= 0.55 THEN 'DISCOUNT'
      WHEN payment_incidents >= 2 THEN 'PAYMENT_PLAN'
      WHEN complaint_cases >= 1 THEN 'CALLBACK'
      WHEN bad_claim_experiences >= 1 THEN 'CLAIM_REVIEW'
      WHEN customer_segment = 'HIGH_VALUE' THEN 'LOYALTY_BONUS'
      ELSE 'COVERAGE_UPGRADE'
    END AS action_type,
    CASE
      WHEN premium_increase_pct_last_renewal >= 0.10 THEN 'PREMIUM_INCREASE'
      WHEN payment_incidents >= 2 THEN 'PAYMENT_INCIDENT'
      WHEN complaint_cases >= 1 THEN 'COMPLAINT'
      WHEN bad_claim_experiences >= 1 THEN 'POOR_CLAIM_EXPERIENCE'
      WHEN customer_segment = 'LOW_ENGAGEMENT' THEN 'LOW_ENGAGEMENT'
      WHEN customer_segment = 'HIGH_VALUE' THEN 'HIGH_VALUE_SAVE'
      ELSE 'RENEWAL_RISK'
    END AS trigger_reason,
    CASE
      WHEN preferred_channel_id IN ('CH_MOBILE', 'CH_EMAIL', 'CH_SMS') THEN preferred_channel_id
      ELSE 'CH_RETENTION_OUTBOUND'
    END AS channel_id
  FROM selected_actions
),
agent_ranked AS (
  SELECT
    agent_id,
    row_number() OVER (ORDER BY agent_id) AS agent_rank,
    count(*) OVER () AS agent_count
  FROM retainflow.silver.dim_agent
  WHERE agent_role IN ('RETENTION', 'HYBRID', 'SERVICE')
)
SELECT
  concat('RET_', substr(sha2(concat_ws('|', customer_id, policy_id, action_type, trigger_reason), 256), 1, 16)) AS retention_action_id,
  customer_id,
  policy_id,
  date_add(history_start_date, CAST(floor(r_date * greatest(datediff(history_end_date, history_start_date), 1)) AS INT)) AS action_date,
  CAST(date_add(history_start_date, CAST(floor(r_date * greatest(datediff(history_end_date, history_start_date), 1)) AS INT)) AS TIMESTAMP) AS action_timestamp,
  action_type,
  trigger_reason,
  CAST(round(
    CASE
      WHEN action_type = 'DISCOUNT' THEN annual_premium * (0.04 + r_value * 0.12)
      WHEN action_type = 'PAYMENT_PLAN' THEN annual_premium / 12.0
      WHEN action_type = 'LOYALTY_BONUS' THEN 40 + r_value * 160
      WHEN action_type = 'COVERAGE_UPGRADE' THEN annual_premium * (0.03 + r_value * 0.05)
      ELSE 0.00
    END,
    2
  ) AS DECIMAL(12,2)) AS offered_value,
  channel_id,
  a.agent_id,
  r_accept < least(
    0.78,
    greatest(
      0.08,
      0.22
      + loyalty_score * 0.24
      + CASE WHEN action_type IN ('DISCOUNT', 'PAYMENT_PLAN') AND price_sensitivity_score > 0.55 THEN 0.20 ELSE 0.00 END
      + CASE WHEN action_type = 'CLAIM_REVIEW' AND bad_claim_experiences > 0 THEN 0.18 ELSE 0.00 END
      - service_sensitivity_score * 0.06
    )
  ) AS accepted_flag,
  r_retained < least(
    0.86,
    greatest(
      0.18,
      0.34
      + loyalty_score * 0.18
      + CASE WHEN r_accept < 0.52 THEN 0.18 ELSE 0.00 END
      + CASE WHEN action_type IN ('DISCOUNT', 'PAYMENT_PLAN', 'CLAIM_REVIEW') THEN 0.10 ELSE 0.00 END
      - price_sensitivity_score * 0.08
    )
  ) AS retained_90d_flag,
  current_timestamp() AS created_at,
  current_timestamp() AS updated_at
FROM action_typed act
LEFT JOIN agent_ranked a
  ON a.agent_rank = 1 + pmod(xxhash64(act.customer_id, act.policy_id, act.action_type), a.agent_count);

INSERT INTO retainflow.monitoring.generation_batches
SELECT
  concat('BATCH_RETENTION_ACTIONS_', date_format(current_timestamp(), 'yyyyMMddHHmmss')) AS batch_id,
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
