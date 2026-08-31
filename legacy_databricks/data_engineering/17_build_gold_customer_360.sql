-- RetainFlow - Phase 1 Gold Customer 360 snapshot
-- Run after 15_generate_retention_actions.sql.

DELETE FROM retainflow.gold.customer_360_snapshot;

INSERT INTO retainflow.gold.customer_360_snapshot
WITH cfg AS (
  SELECT snapshot_date
  FROM retainflow.monitoring.generation_config
  WHERE is_active = true
),
customers AS (
  SELECT
    c.customer_id,
    c.acquisition_date,
    c.customer_segment,
    c.price_sensitivity_score,
    c.digital_engagement_score,
    c.loyalty_score,
    cfg.snapshot_date
  FROM retainflow.silver.dim_customer c
  CROSS JOIN cfg
),
policy_features AS (
  SELECT
    c.customer_id,
    count(DISTINCT CASE WHEN p.policy_status = 'ACTIVE' THEN p.policy_id END) AS active_policy_count,
    count(DISTINCT CASE WHEN p.policy_status = 'ACTIVE' THEN pr.product_family END) AS number_of_products,
    CAST(coalesce(sum(CASE WHEN p.policy_status = 'ACTIVE' THEN p.annual_premium ELSE 0 END), 0) AS DECIMAL(14,2)) AS total_annual_premium,
    max(CASE
      WHEN p.policy_start_date <= c.snapshot_date
       AND p.premium_increase_pct_last_renewal IS NOT NULL
      THEN p.premium_increase_pct_last_renewal
      ELSE 0.0
    END) AS premium_increase_pct_max_12m,
    min(CASE
      WHEN p.next_renewal_date >= c.snapshot_date THEN datediff(p.next_renewal_date, c.snapshot_date)
      ELSE NULL
    END) AS renewal_days_min
  FROM customers c
  LEFT JOIN retainflow.silver.fact_policy p
    ON c.customer_id = p.customer_id
   AND p.policy_start_date <= c.snapshot_date
  LEFT JOIN retainflow.silver.dim_product pr
    ON p.product_id = pr.product_id
  GROUP BY c.customer_id
),
claim_features AS (
  SELECT
    c.customer_id,
    count(DISTINCT clm.claim_id) AS total_claims_12m,
    CAST(coalesce(sum(clm.claim_amount), 0) AS DECIMAL(14,2)) AS total_claim_amount_12m,
    avg(clm.claim_satisfaction_score) AS avg_claim_satisfaction_12m
  FROM customers c
  LEFT JOIN retainflow.silver.fact_claims clm
    ON c.customer_id = clm.customer_id
   AND clm.claim_date > add_months(c.snapshot_date, -12)
   AND clm.claim_date <= c.snapshot_date
  GROUP BY c.customer_id
),
payment_features AS (
  SELECT
    c.customer_id,
    count(DISTINCT CASE WHEN pay.payment_status IN ('LATE', 'REJECTED', 'WRITTEN_OFF') THEN pay.payment_id END) AS payment_incidents_6m
  FROM customers c
  LEFT JOIN retainflow.silver.fact_payments pay
    ON c.customer_id = pay.customer_id
   AND pay.due_date > add_months(c.snapshot_date, -6)
   AND pay.due_date <= c.snapshot_date
  GROUP BY c.customer_id
),
service_features AS (
  SELECT
    c.customer_id,
    count(DISTINCT CASE WHEN cs.case_type IN ('COMPLAINT', 'CANCELLATION_INTENT') THEN cs.case_id END) AS complaints_6m,
    avg(cs.satisfaction_score) AS avg_service_satisfaction_12m
  FROM customers c
  LEFT JOIN retainflow.silver.fact_customer_service cs
    ON c.customer_id = cs.customer_id
   AND to_date(cs.opened_datetime) > add_months(c.snapshot_date, -12)
   AND to_date(cs.opened_datetime) <= c.snapshot_date
  GROUP BY c.customer_id
),
interaction_features AS (
  SELECT
    c.customer_id,
    count(DISTINCT CASE WHEN i.interaction_datetime > add_months(CAST(c.snapshot_date AS TIMESTAMP), -3) THEN i.interaction_id END) AS interactions_3m,
    datediff(c.snapshot_date, max(to_date(i.interaction_datetime))) AS days_since_last_contact,
    count(DISTINCT CASE
      WHEN i.interaction_type IN ('WEB_VISIT', 'MOBILE_SESSION')
       AND to_date(i.interaction_datetime) > date_sub(c.snapshot_date, 30)
      THEN i.interaction_id
    END) AS digital_sessions_30d
  FROM customers c
  LEFT JOIN retainflow.silver.fact_interactions i
    ON c.customer_id = i.customer_id
   AND to_date(i.interaction_datetime) <= c.snapshot_date
  GROUP BY c.customer_id, c.snapshot_date
),
campaign_features AS (
  SELECT
    c.customer_id,
    CASE
      WHEN count(DISTINCT CASE WHEN cc.channel_id = 'CH_EMAIL' THEN cc.campaign_contact_id END) = 0 THEN 0.0
      ELSE count(DISTINCT CASE WHEN cc.channel_id = 'CH_EMAIL' AND cc.opened_flag THEN cc.campaign_contact_id END)
        / count(DISTINCT CASE WHEN cc.channel_id = 'CH_EMAIL' THEN cc.campaign_contact_id END)
    END AS email_open_rate_6m
  FROM customers c
  LEFT JOIN retainflow.silver.fact_campaign_contact cc
    ON c.customer_id = cc.customer_id
   AND to_date(cc.contact_datetime) > add_months(c.snapshot_date, -6)
   AND to_date(cc.contact_datetime) <= c.snapshot_date
  GROUP BY c.customer_id
),
retention_features AS (
  SELECT
    c.customer_id,
    count(DISTINCT ra.retention_action_id) AS retention_actions_12m,
    count(DISTINCT CASE WHEN ra.accepted_flag THEN ra.retention_action_id END) AS accepted_retention_actions_12m
  FROM customers c
  LEFT JOIN retainflow.silver.fact_retention_actions ra
    ON c.customer_id = ra.customer_id
   AND ra.action_date > add_months(c.snapshot_date, -12)
   AND ra.action_date <= c.snapshot_date
  GROUP BY c.customer_id
),
feature_joined AS (
  SELECT
    c.snapshot_date AS observation_date,
    c.customer_id,
    CAST(floor(months_between(c.snapshot_date, c.acquisition_date)) AS INT) AS tenure_months,
    coalesce(p.active_policy_count, 0) AS active_policy_count,
    coalesce(p.number_of_products, 0) AS number_of_products,
    coalesce(p.total_annual_premium, CAST(0 AS DECIMAL(14,2))) AS total_annual_premium,
    coalesce(cl.total_claims_12m, 0) AS total_claims_12m,
    coalesce(cl.total_claim_amount_12m, CAST(0 AS DECIMAL(14,2))) AS total_claim_amount_12m,
    coalesce(pay.payment_incidents_6m, 0) AS payment_incidents_6m,
    coalesce(svc.complaints_6m, 0) AS complaints_6m,
    coalesce(i.interactions_3m, 0) AS interactions_3m,
    coalesce(i.days_since_last_contact, 9999) AS days_since_last_contact,
    coalesce(i.digital_sessions_30d, 0) AS digital_sessions_30d,
    coalesce(cc.email_open_rate_6m, 0.0) AS email_open_rate_6m,
    coalesce(p.premium_increase_pct_max_12m, 0.0) AS premium_increase_pct_max_12m,
    coalesce(
      (coalesce(cl.avg_claim_satisfaction_12m, svc.avg_service_satisfaction_12m) + coalesce(svc.avg_service_satisfaction_12m, cl.avg_claim_satisfaction_12m)) / 2.0,
      4.0
    ) AS avg_satisfaction_score_12m,
    coalesce(p.renewal_days_min, 9999) AS renewal_days_min,
    c.customer_segment,
    c.price_sensitivity_score,
    c.digital_engagement_score,
    c.loyalty_score,
    coalesce(r.retention_actions_12m, 0) AS retention_actions_12m,
    coalesce(r.accepted_retention_actions_12m, 0) AS accepted_retention_actions_12m
  FROM customers c
  LEFT JOIN policy_features p ON c.customer_id = p.customer_id
  LEFT JOIN claim_features cl ON c.customer_id = cl.customer_id
  LEFT JOIN payment_features pay ON c.customer_id = pay.customer_id
  LEFT JOIN service_features svc ON c.customer_id = svc.customer_id
  LEFT JOIN interaction_features i ON c.customer_id = i.customer_id
  LEFT JOIN campaign_features cc ON c.customer_id = cc.customer_id
  LEFT JOIN retention_features r ON c.customer_id = r.customer_id
),
scored AS (
  SELECT
    *,
    least(
      100.0,
      greatest(
        0.0,
        total_annual_premium / 35.0
        + active_policy_count * 6.0
        + number_of_products * 8.0
        + loyalty_score * 18.0
        - payment_incidents_6m * 4.0
        - complaints_6m * 5.0
      )
    ) AS customer_value_score,
    (
      0.20
      + price_sensitivity_score * 0.25
      + premium_increase_pct_max_12m * 1.40
      + payment_incidents_6m * 0.10
      + complaints_6m * 0.14
      + CASE WHEN avg_satisfaction_score_12m < 3.2 THEN 0.18 ELSE 0.00 END
      + CASE WHEN days_since_last_contact > 180 THEN 0.10 ELSE 0.00 END
      + CASE WHEN number_of_products <= 1 THEN 0.08 ELSE -0.06 END
      + CASE WHEN renewal_days_min BETWEEN 0 AND 90 THEN 0.16 ELSE 0.00 END
      - accepted_retention_actions_12m * 0.08
      - loyalty_score * 0.12
    ) AS latent_churn_score
  FROM feature_joined
)
SELECT
  observation_date,
  customer_id,
  tenure_months,
  active_policy_count,
  number_of_products,
  total_annual_premium,
  total_claims_12m,
  total_claim_amount_12m,
  payment_incidents_6m,
  complaints_6m,
  interactions_3m,
  days_since_last_contact,
  digital_sessions_30d,
  email_open_rate_6m,
  premium_increase_pct_max_12m,
  avg_satisfaction_score_12m,
  renewal_days_min,
  customer_value_score,
  CASE
    WHEN latent_churn_score >= 0.78 THEN 'VERY_HIGH'
    WHEN latent_churn_score >= 0.58 THEN 'HIGH'
    WHEN latent_churn_score >= 0.38 THEN 'MEDIUM'
    ELSE 'LOW'
  END AS latent_churn_risk_band,
  current_timestamp() AS created_at
FROM scored;

INSERT INTO retainflow.monitoring.generation_batches
SELECT
  concat('BATCH_CUSTOMER_360_', date_format(current_timestamp(), 'yyyyMMddHHmmss')) AS batch_id,
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
