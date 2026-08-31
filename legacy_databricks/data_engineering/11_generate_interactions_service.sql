-- RetainFlow - Phase 1 synthetic interactions and customer service generation
-- Run after 09_generate_claims.sql.

DELETE FROM retainflow.silver.fact_customer_service;
DELETE FROM retainflow.silver.fact_interactions;

INSERT INTO retainflow.silver.fact_interactions
WITH cfg AS (
  SELECT history_start_date, history_end_date, snapshot_date
  FROM retainflow.monitoring.generation_config
  WHERE is_active = true
),
customers AS (
  SELECT c.*, cfg.history_start_date, cfg.history_end_date, cfg.snapshot_date
  FROM retainflow.silver.dim_customer c
  CROSS JOIN cfg
),
baseline_candidates AS (
  SELECT
    c.customer_id,
    CAST(NULL AS STRING) AS policy_id,
    c.preferred_channel_id AS channel_id,
    c.digital_profile,
    c.customer_segment,
    c.service_sensitivity_score,
    c.digital_engagement_score,
    c.history_start_date,
    c.history_end_date,
    interaction_seq,
    rand(501) AS r_keep,
    rand(502) AS r_date,
    rand(503) AS r_type,
    rand(504) AS r_sentiment,
    rand(505) AS r_duration,
    rand(506) AS r_resolved,
    'GENERAL_SERVICE' AS interaction_reason,
    'BASELINE' AS trigger_source
  FROM customers c
  CROSS JOIN (SELECT explode(sequence(1, 10)) AS interaction_seq)
),
baseline_interactions AS (
  SELECT *
  FROM baseline_candidates
  WHERE r_keep < CASE
    WHEN digital_profile = 'HIGH' THEN 0.55
    WHEN digital_profile = 'MEDIUM' THEN 0.38
    ELSE 0.22
  END
),
payment_triggered AS (
  SELECT
    pay.customer_id,
    pay.policy_id,
    CASE WHEN pay.payment_status = 'LATE' THEN 'CH_EMAIL' ELSE 'CH_CALL_CENTER' END AS channel_id,
    c.digital_profile,
    c.customer_segment,
    c.service_sensitivity_score,
    c.digital_engagement_score,
    cfg.history_start_date,
    cfg.history_end_date,
    1000 + row_number() OVER (PARTITION BY pay.customer_id ORDER BY pay.due_date, pay.payment_id) AS interaction_seq,
    rand(511) AS r_keep,
    rand(512) AS r_date,
    rand(513) AS r_type,
    rand(514) AS r_sentiment,
    rand(515) AS r_duration,
    rand(516) AS r_resolved,
    'BILLING' AS interaction_reason,
    'PAYMENT' AS trigger_source
  FROM retainflow.silver.fact_payments pay
  JOIN retainflow.silver.dim_customer c
    ON pay.customer_id = c.customer_id
  CROSS JOIN cfg
  WHERE pay.payment_status IN ('LATE', 'REJECTED', 'WRITTEN_OFF')
),
claim_triggered AS (
  SELECT
    clm.customer_id,
    clm.policy_id,
    CASE WHEN clm.claim_status IN ('REJECTED', 'UNDER_REVIEW') THEN 'CH_CALL_CENTER' ELSE c.preferred_channel_id END AS channel_id,
    c.digital_profile,
    c.customer_segment,
    c.service_sensitivity_score,
    c.digital_engagement_score,
    cfg.history_start_date,
    cfg.history_end_date,
    2000 + row_number() OVER (PARTITION BY clm.customer_id ORDER BY clm.claim_date, clm.claim_id) AS interaction_seq,
    rand(521) AS r_keep,
    rand(522) AS r_date,
    rand(523) AS r_type,
    rand(524) AS r_sentiment,
    rand(525) AS r_duration,
    rand(526) AS r_resolved,
    CASE WHEN clm.claim_status = 'REJECTED' THEN 'COMPLAINT' ELSE 'CLAIM' END AS interaction_reason,
    'CLAIM' AS trigger_source
  FROM retainflow.silver.fact_claims clm
  JOIN retainflow.silver.dim_customer c
    ON clm.customer_id = c.customer_id
  CROSS JOIN cfg
),
renewal_triggered AS (
  SELECT
    p.customer_id,
    p.policy_id,
    c.preferred_channel_id AS channel_id,
    c.digital_profile,
    c.customer_segment,
    c.service_sensitivity_score,
    c.digital_engagement_score,
    cfg.history_start_date,
    cfg.history_end_date,
    3000 + row_number() OVER (PARTITION BY p.customer_id ORDER BY p.next_renewal_date, p.policy_id) AS interaction_seq,
    rand(531) AS r_keep,
    rand(532) AS r_date,
    rand(533) AS r_type,
    rand(534) AS r_sentiment,
    rand(535) AS r_duration,
    rand(536) AS r_resolved,
    CASE WHEN p.premium_increase_pct_last_renewal >= 0.12 THEN 'RETENTION' ELSE 'RENEWAL' END AS interaction_reason,
    'RENEWAL' AS trigger_source
  FROM retainflow.silver.fact_policy p
  JOIN retainflow.silver.dim_customer c
    ON p.customer_id = c.customer_id
  CROSS JOIN cfg
  WHERE p.next_renewal_date IS NOT NULL
),
all_interactions AS (
  SELECT * FROM baseline_interactions
  UNION ALL
  SELECT * FROM payment_triggered WHERE r_keep < 0.55
  UNION ALL
  SELECT * FROM claim_triggered WHERE r_keep < 0.70
  UNION ALL
  SELECT * FROM renewal_triggered WHERE r_keep < CASE WHEN interaction_reason = 'RETENTION' THEN 0.75 ELSE 0.38 END
),
agent_ranked AS (
  SELECT
    agent_id,
    channel_id,
    row_number() OVER (PARTITION BY channel_id ORDER BY agent_id) AS agent_rank,
    count(*) OVER (PARTITION BY channel_id) AS agent_count
  FROM retainflow.silver.dim_agent
)
SELECT
  concat('INT_', substr(sha2(concat_ws('|', i.customer_id, coalesce(i.policy_id, 'NA'), i.trigger_source, CAST(i.interaction_seq AS STRING)), 256), 1, 16)) AS interaction_id,
  i.customer_id,
  i.policy_id,
  i.channel_id,
  a.agent_id,
  CAST(date_add(i.history_start_date, CAST(floor(i.r_date * greatest(datediff(i.history_end_date, i.history_start_date), 1)) AS INT)) AS TIMESTAMP) AS interaction_datetime,
  year(date_add(i.history_start_date, CAST(floor(i.r_date * greatest(datediff(i.history_end_date, i.history_start_date), 1)) AS INT))) AS interaction_year,
  CASE
    WHEN i.channel_id = 'CH_MOBILE' THEN 'MOBILE_SESSION'
    WHEN i.channel_id = 'CH_WEB' THEN 'WEB_VISIT'
    WHEN i.channel_id = 'CH_EMAIL' THEN 'EMAIL'
    WHEN i.channel_id = 'CH_SMS' THEN 'SMS'
    WHEN i.channel_id = 'CH_BRANCH' THEN 'BRANCH_MEETING'
    ELSE 'CALL'
  END AS interaction_type,
  i.interaction_reason,
  CASE WHEN i.trigger_source IN ('PAYMENT', 'RENEWAL') THEN 'OUTBOUND' ELSE 'INBOUND' END AS direction,
  CASE
    WHEN i.channel_id IN ('CH_WEB', 'CH_MOBILE') THEN CAST(60 + floor(i.r_duration * 900) AS INT)
    WHEN i.channel_id IN ('CH_EMAIL', 'CH_SMS') THEN CAST(5 + floor(i.r_duration * 120) AS INT)
    ELSE CAST(120 + floor(i.r_duration * 1800) AS INT)
  END AS duration_seconds,
  least(
    1.0,
    greatest(
      -1.0,
      0.35
      - CASE WHEN i.interaction_reason IN ('COMPLAINT', 'BILLING', 'RETENTION') THEN 0.55 ELSE 0.00 END
      - i.service_sensitivity_score * 0.25
      + i.digital_engagement_score * 0.12
      + i.r_sentiment * 0.60
    )
  ) AS sentiment_score,
  i.r_resolved > CASE WHEN i.interaction_reason = 'COMPLAINT' THEN 0.28 WHEN i.interaction_reason = 'BILLING' THEN 0.18 ELSE 0.10 END AS resolved_flag,
  current_timestamp() AS created_at
FROM all_interactions i
LEFT JOIN agent_ranked a
  ON i.channel_id = a.channel_id
 AND a.agent_rank = 1 + pmod(xxhash64(i.customer_id, coalesce(i.policy_id, 'NA'), i.trigger_source), a.agent_count);

INSERT INTO retainflow.silver.fact_customer_service
WITH interactions AS (
  SELECT
    i.*,
    c.service_sensitivity_score,
    c.price_sensitivity_score,
    rand(601) AS r_case,
    rand(602) AS r_priority,
    rand(603) AS r_sla,
    rand(604) AS r_resolution,
    rand(605) AS r_satisfaction
  FROM retainflow.silver.fact_interactions i
  JOIN retainflow.silver.dim_customer c
    ON i.customer_id = c.customer_id
  WHERE i.interaction_reason IN ('CLAIM', 'COMPLAINT', 'BILLING', 'RETENTION', 'GENERAL_SERVICE')
),
selected_cases AS (
  SELECT *
  FROM interactions
  WHERE r_case < CASE
    WHEN interaction_reason = 'COMPLAINT' THEN 0.88
    WHEN interaction_reason = 'BILLING' THEN 0.44
    WHEN interaction_reason = 'CLAIM' THEN 0.38
    WHEN interaction_reason = 'RETENTION' THEN 0.30
    ELSE 0.12
  END
),
case_final AS (
  SELECT
    *,
    CASE
      WHEN interaction_reason = 'COMPLAINT' THEN 'COMPLAINT'
      WHEN interaction_reason = 'BILLING' THEN 'BILLING'
      WHEN interaction_reason = 'CLAIM' THEN 'CLAIM_SUPPORT'
      WHEN interaction_reason = 'RETENTION' AND price_sensitivity_score > 0.68 THEN 'CANCELLATION_INTENT'
      ELSE 'REQUEST'
    END AS case_type,
    CASE
      WHEN r_priority < 0.08 THEN 'CRITICAL'
      WHEN r_priority < 0.28 THEN 'HIGH'
      WHEN r_priority < 0.72 THEN 'MEDIUM'
      ELSE 'LOW'
    END AS priority
  FROM selected_cases
)
SELECT
  concat('CASE_', substr(sha2(concat_ws('|', interaction_id, customer_id, coalesce(policy_id, 'NA')), 256), 1, 16)) AS case_id,
  customer_id,
  policy_id,
  interaction_id,
  interaction_datetime AS opened_datetime,
  CASE
    WHEN r_resolution < 0.08 THEN NULL
    ELSE interaction_datetime + make_interval(0, 0, 0, CAST(1 + floor(r_resolution * 21) AS INT), 0, 0, 0)
  END AS closed_datetime,
  case_type,
  priority,
  CASE
    WHEN r_resolution < 0.08 THEN 'OPEN'
    WHEN r_resolution < 0.16 THEN 'IN_PROGRESS'
    WHEN r_resolution < 0.24 THEN 'ESCALATED'
    WHEN r_resolution < 0.88 THEN 'RESOLVED'
    ELSE 'CLOSED'
  END AS case_status,
  r_sla < CASE WHEN priority IN ('CRITICAL', 'HIGH') THEN 0.18 WHEN case_type = 'COMPLAINT' THEN 0.22 ELSE 0.09 END AS sla_breached_flag,
  CASE
    WHEN r_resolution < 0.08 THEN NULL
    WHEN case_type = 'COMPLAINT' AND r_resolution < 0.35 THEN 'GESTURE_OFFERED'
    WHEN case_type = 'BILLING' THEN 'PAYMENT_CLARIFIED'
    WHEN case_type = 'CLAIM_SUPPORT' THEN 'CLAIM_STATUS_EXPLAINED'
    WHEN case_type = 'CANCELLATION_INTENT' THEN 'RETENTION_ESCALATION'
    ELSE 'INFORMATION_PROVIDED'
  END AS resolution_code,
  least(
    5.0,
    greatest(
      1.0,
      4.5
      + sentiment_score
      - CASE WHEN case_type = 'COMPLAINT' THEN 0.75 ELSE 0.00 END
      - CASE WHEN r_sla < 0.18 THEN 0.65 ELSE 0.00 END
      - service_sensitivity_score * 0.35
      + r_satisfaction * 0.40
    )
  ) AS satisfaction_score,
  current_timestamp() AS created_at,
  current_timestamp() AS updated_at
FROM case_final;

INSERT INTO retainflow.monitoring.generation_batches
SELECT
  concat('BATCH_INTERACTIONS_SERVICE_', date_format(current_timestamp(), 'yyyyMMddHHmmss')) AS batch_id,
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
