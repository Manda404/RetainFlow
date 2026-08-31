-- RetainFlow - Phase 1 synthetic marketing campaign and quote generation
-- Run after 11_generate_interactions_service.sql.

DELETE FROM retainflow.silver.fact_quotes;
DELETE FROM retainflow.silver.fact_campaign_contact;

INSERT INTO retainflow.silver.fact_campaign_contact
WITH cfg AS (
  SELECT history_start_date, history_end_date, snapshot_date
  FROM retainflow.monitoring.generation_config
  WHERE is_active = true
),
customer_policy_summary AS (
  SELECT
    c.customer_id,
    c.customer_segment,
    c.digital_profile,
    c.preferred_channel_id,
    c.consent_email,
    c.consent_sms,
    c.consent_phone,
    c.digital_engagement_score,
    c.price_sensitivity_score,
    c.loyalty_score,
    cfg.history_start_date,
    cfg.history_end_date,
    count(DISTINCT p.policy_id) AS policy_count,
    min(p.next_renewal_date) AS next_renewal_date,
    max(CASE WHEN p.premium_increase_pct_last_renewal >= 0.10 THEN 1 ELSE 0 END) AS has_premium_increase,
    max(CASE WHEN p.policy_status = 'CANCELLED' THEN 1 ELSE 0 END) AS has_cancelled_policy
  FROM retainflow.silver.dim_customer c
  LEFT JOIN retainflow.silver.fact_policy p
    ON c.customer_id = p.customer_id
  CROSS JOIN cfg
  GROUP BY
    c.customer_id,
    c.customer_segment,
    c.digital_profile,
    c.preferred_channel_id,
    c.consent_email,
    c.consent_sms,
    c.consent_phone,
    c.digital_engagement_score,
    c.price_sensitivity_score,
    c.loyalty_score,
    cfg.history_start_date,
    cfg.history_end_date
),
campaign_candidates AS (
  SELECT
    *,
    campaign_seq,
    rand(701) AS r_keep,
    rand(702) AS r_date,
    rand(703) AS r_channel,
    rand(704) AS r_open,
    rand(705) AS r_click,
    rand(706) AS r_response,
    rand(707) AS r_convert,
    rand(708) AS r_campaign
  FROM customer_policy_summary
  CROSS JOIN (SELECT explode(sequence(1, 6)) AS campaign_seq)
),
campaign_selected AS (
  SELECT *
  FROM campaign_candidates
  WHERE r_keep < CASE
    WHEN customer_segment = 'HIGH_VALUE' THEN 0.58
    WHEN customer_segment = 'DIGITAL_FIRST' THEN 0.52
    WHEN customer_segment = 'PRICE_SENSITIVE' THEN 0.45
    WHEN policy_count <= 1 THEN 0.42
    ELSE 0.32
  END
),
campaign_typed AS (
  SELECT
    *,
    CASE
      WHEN has_cancelled_policy = 1 THEN 'WINBACK'
      WHEN has_premium_increase = 1 OR customer_segment = 'PRICE_SENSITIVE' THEN 'RETENTION'
      WHEN policy_count <= 1 THEN 'CROSS_SELL'
      WHEN r_campaign < 0.25 THEN 'UPSELL'
      WHEN r_campaign < 0.65 THEN 'RENEWAL'
      ELSE 'CROSS_SELL'
    END AS campaign_type,
    CASE
      WHEN consent_email AND r_channel < 0.55 THEN 'CH_EMAIL'
      WHEN consent_sms AND r_channel < 0.72 THEN 'CH_SMS'
      WHEN digital_profile = 'HIGH' AND r_channel < 0.90 THEN 'CH_MOBILE'
      WHEN consent_phone THEN 'CH_CALL_CENTER'
      ELSE preferred_channel_id
    END AS channel_id
  FROM campaign_selected
),
campaign_final AS (
  SELECT
    *,
    least(0.95, greatest(0.05, 0.20 + digital_engagement_score * 0.45 + CASE WHEN channel_id IN ('CH_EMAIL', 'CH_MOBILE') THEN 0.12 ELSE -0.05 END)) AS open_probability,
    least(0.70, greatest(0.02, 0.05 + digital_engagement_score * 0.28 + CASE WHEN campaign_type IN ('RETENTION', 'RENEWAL') THEN 0.08 ELSE 0.00 END)) AS click_probability,
    least(0.55, greatest(0.01, 0.03 + loyalty_score * 0.18 + CASE WHEN campaign_type = 'RETENTION' THEN 0.10 ELSE 0.00 END)) AS response_probability,
    least(0.38, greatest(0.005, 0.02 + loyalty_score * 0.12 - price_sensitivity_score * 0.06 + CASE WHEN campaign_type = 'CROSS_SELL' THEN 0.05 ELSE 0.00 END)) AS conversion_probability
  FROM campaign_typed
)
SELECT
  concat('CMPCT_', substr(sha2(concat_ws('|', customer_id, campaign_type, CAST(campaign_seq AS STRING)), 256), 1, 16)) AS campaign_contact_id,
  concat('CMP_', campaign_type, '_', CAST(2021 + pmod(xxhash64(customer_id, CAST(campaign_seq AS STRING)), 5) AS STRING)) AS campaign_id,
  customer_id,
  CAST(NULL AS STRING) AS policy_id,
  channel_id,
  campaign_type,
  CASE
    WHEN campaign_type = 'RETENTION' THEN 'Retention save offer'
    WHEN campaign_type = 'RENEWAL' THEN 'Renewal reminder'
    WHEN campaign_type = 'CROSS_SELL' THEN 'Multi-product protection'
    WHEN campaign_type = 'UPSELL' THEN 'Coverage upgrade'
    WHEN campaign_type = 'WINBACK' THEN 'Winback proposal'
    ELSE 'Acquisition campaign'
  END AS campaign_name,
  CAST(date_add(history_start_date, CAST(floor(r_date * greatest(datediff(history_end_date, history_start_date), 1)) AS INT)) AS TIMESTAMP) AS contact_datetime,
  year(date_add(history_start_date, CAST(floor(r_date * greatest(datediff(history_end_date, history_start_date), 1)) AS INT))) AS contact_year,
  r_open < open_probability AS opened_flag,
  r_open < open_probability AND r_click < click_probability AS clicked_flag,
  r_open < open_probability AND r_response < response_probability AS responded_flag,
  r_open < open_probability AND r_click < click_probability AND r_convert < conversion_probability AS converted_flag,
  concat('OFF_', campaign_type, '_', CAST(1 + pmod(xxhash64(customer_id, campaign_type), 7) AS STRING)) AS offer_id,
  current_timestamp() AS created_at
FROM campaign_final;

INSERT INTO retainflow.silver.fact_quotes
WITH cfg AS (
  SELECT history_start_date, history_end_date
  FROM retainflow.monitoring.generation_config
  WHERE is_active = true
),
campaign_quote_candidates AS (
  SELECT
    cc.campaign_contact_id,
    cc.customer_id,
    cc.channel_id,
    cc.contact_datetime,
    cc.converted_flag,
    c.price_sensitivity_score,
    c.loyalty_score,
    rand(801) AS r_product,
    rand(802) AS r_competitor,
    rand(803) AS r_status,
    'CAMPAIGN' AS quote_source
  FROM retainflow.silver.fact_campaign_contact cc
  JOIN retainflow.silver.dim_customer c
    ON cc.customer_id = c.customer_id
  WHERE cc.clicked_flag OR cc.responded_flag OR cc.converted_flag
),
organic_quote_candidates AS (
  SELECT
    concat('ORG_', c.customer_id, '_', CAST(quote_seq AS STRING)) AS campaign_contact_id,
    c.customer_id,
    c.preferred_channel_id AS channel_id,
    CAST(date_add(cfg.history_start_date, CAST(floor(rand(811) * greatest(datediff(cfg.history_end_date, cfg.history_start_date), 1)) AS INT)) AS TIMESTAMP) AS contact_datetime,
    false AS converted_flag,
    c.price_sensitivity_score,
    c.loyalty_score,
    rand(812) AS r_product,
    rand(813) AS r_competitor,
    rand(814) AS r_status,
    'ORGANIC' AS quote_source
  FROM retainflow.silver.dim_customer c
  CROSS JOIN cfg
  CROSS JOIN (SELECT explode(sequence(1, 2)) AS quote_seq)
  WHERE rand(815) < CASE WHEN c.digital_profile = 'HIGH' THEN 0.16 WHEN c.digital_profile = 'MEDIUM' THEN 0.10 ELSE 0.06 END
),
all_quote_candidates AS (
  SELECT * FROM campaign_quote_candidates
  UNION ALL
  SELECT * FROM organic_quote_candidates
),
product_ranked AS (
  SELECT
    product_id,
    product_family,
    coverage_tier,
    base_annual_premium,
    row_number() OVER (ORDER BY product_family, coverage_tier) AS product_rank,
    count(*) OVER () AS product_count
  FROM retainflow.silver.dim_product
  WHERE is_active = true
),
quote_with_product AS (
  SELECT
    q.*,
    p.product_id,
    p.base_annual_premium,
    p.coverage_tier
  FROM all_quote_candidates q
  JOIN product_ranked p
    ON p.product_rank = 1 + pmod(xxhash64(q.customer_id, q.campaign_contact_id), p.product_count)
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
  concat('QTE_', substr(sha2(concat_ws('|', q.customer_id, q.campaign_contact_id, q.product_id), 256), 1, 16)) AS quote_id,
  q.customer_id,
  q.product_id,
  q.channel_id,
  a.agent_id,
  to_date(q.contact_datetime) AS quote_date,
  CAST(round(q.base_annual_premium * (0.82 + q.r_product * 0.55) * CASE WHEN q.coverage_tier = 'PREMIUM' THEN 1.12 WHEN q.coverage_tier = 'BASIC' THEN 0.92 ELSE 1.00 END, 2) AS DECIMAL(12,2)) AS quoted_annual_premium,
  round(0.72 + q.r_competitor * 0.62 + q.price_sensitivity_score * 0.10, 4) AS competitor_price_index,
  CASE
    WHEN q.converted_flag THEN 'ACCEPTED'
    WHEN q.r_status < 0.18 + q.loyalty_score * 0.12 THEN 'SENT'
    WHEN q.r_status < 0.32 + q.loyalty_score * 0.10 THEN 'ACCEPTED'
    WHEN q.r_status < 0.74 THEN 'DECLINED'
    ELSE 'EXPIRED'
  END AS quote_status,
  CAST(NULL AS STRING) AS converted_policy_id,
  current_timestamp() AS created_at,
  current_timestamp() AS updated_at
FROM quote_with_product q
LEFT JOIN agent_ranked a
  ON q.channel_id = a.channel_id
 AND a.agent_rank = 1 + pmod(xxhash64(q.customer_id, q.campaign_contact_id), a.agent_count);

INSERT INTO retainflow.monitoring.generation_batches
SELECT
  concat('BATCH_MARKETING_QUOTES_', date_format(current_timestamp(), 'yyyyMMddHHmmss')) AS batch_id,
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
