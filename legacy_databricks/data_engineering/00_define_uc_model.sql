-- RetainFlow - Phase 1 Unity Catalog and Delta table model
-- Run in Databricks SQL or a Databricks notebook SQL cell.
--
-- If Databricks Free Edition does not allow CREATE CATALOG, create/use an
-- existing catalog and replace `retainflow` below with that catalog name.

CREATE CATALOG IF NOT EXISTS retainflow
COMMENT 'RetainFlow synthetic insurance retention platform.';

CREATE SCHEMA IF NOT EXISTS retainflow.raw
COMMENT 'Landing area for generated source-system extracts with intentional imperfections.';

CREATE SCHEMA IF NOT EXISTS retainflow.bronze
COMMENT 'Append-oriented raw-like Delta tables with ingestion metadata.';

CREATE SCHEMA IF NOT EXISTS retainflow.silver
COMMENT 'Clean insurance enterprise data model: standardized, typed, deduplicated, and coherent.';

CREATE SCHEMA IF NOT EXISTS retainflow.gold
COMMENT 'Analytics-ready customer and retention marts.';

CREATE SCHEMA IF NOT EXISTS retainflow.ml
COMMENT 'Reserved for churn feature tables, labels, model outputs, and scoring results.';

CREATE SCHEMA IF NOT EXISTS retainflow.monitoring
COMMENT 'Data quality, generation, pipeline, ML, agentic, and business monitoring.';

CREATE TABLE IF NOT EXISTS retainflow.silver.dim_date (
  date_key INT COMMENT 'Date key in yyyyMMdd format.',
  calendar_date DATE COMMENT 'Calendar date.',
  calendar_year INT,
  calendar_quarter INT,
  calendar_month INT,
  month_name STRING,
  day_of_month INT,
  day_of_week INT,
  week_of_year INT,
  is_weekend BOOLEAN,
  is_month_end BOOLEAN,
  is_quarter_end BOOLEAN,
  is_year_end BOOLEAN
)
USING DELTA
COMMENT 'Shared date dimension for reporting, renewals, payments, claims, and time-windowed features.';

CREATE TABLE IF NOT EXISTS retainflow.silver.dim_geography (
  geography_id STRING COMMENT 'Stable geography identifier.',
  country STRING,
  region STRING,
  department STRING,
  city STRING,
  postal_code STRING,
  urbanicity STRING COMMENT 'URBAN, SUBURBAN, or RURAL.',
  income_index DOUBLE COMMENT 'Synthetic regional income index.',
  claim_risk_index DOUBLE COMMENT 'Synthetic regional claim risk index.',
  digital_adoption_index DOUBLE COMMENT 'Synthetic regional digital adoption index.',
  created_at TIMESTAMP,
  updated_at TIMESTAMP
)
USING DELTA
COMMENT 'Geographic segmentation used by customers, agents, pricing, claims, and retention behavior.';

CREATE TABLE IF NOT EXISTS retainflow.silver.dim_channel (
  channel_id STRING COMMENT 'Stable channel identifier.',
  channel_code STRING COMMENT 'WEB, MOBILE, BRANCH, CALL_CENTER, BROKER, PARTNER, EMAIL, SMS, RETENTION_OUTBOUND.',
  channel_name STRING,
  channel_family STRING COMMENT 'DIGITAL, HUMAN, PARTNER, or OUTBOUND.',
  is_digital BOOLEAN,
  is_inbound BOOLEAN,
  is_active BOOLEAN,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
)
USING DELTA
COMMENT 'Reference channels for acquisition, policy sales, service, marketing, quotes, and retention actions.';

CREATE TABLE IF NOT EXISTS retainflow.silver.dim_agent (
  agent_id STRING COMMENT 'Stable sales, service, claims, or retention agent identifier.',
  source_agent_id STRING,
  agent_name STRING,
  agent_role STRING COMMENT 'SALES, SERVICE, CLAIMS, RETENTION, or HYBRID.',
  channel_id STRING COMMENT 'Logical FK to dim_channel.channel_id.',
  geography_id STRING COMMENT 'Logical FK to dim_geography.geography_id.',
  team_name STRING,
  hire_date DATE,
  is_active BOOLEAN,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
)
USING DELTA
COMMENT 'Agents and teams connected to policies, interactions, service cases, and retention actions.';

CREATE TABLE IF NOT EXISTS retainflow.silver.dim_product (
  product_id STRING COMMENT 'Stable insurance product identifier.',
  product_family STRING COMMENT 'AUTO, HOME, HEALTH, LIFE, TRAVEL, PET, or PERSONAL_ACCIDENT.',
  product_name STRING,
  coverage_tier STRING COMMENT 'BASIC, STANDARD, or PREMIUM.',
  base_annual_premium DECIMAL(12,2),
  deductible_amount DECIMAL(12,2),
  risk_level STRING COMMENT 'LOW, MEDIUM, HIGH, or VERY_HIGH.',
  default_payment_frequency STRING COMMENT 'MONTHLY, QUARTERLY, or ANNUAL.',
  is_active BOOLEAN,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
)
USING DELTA
COMMENT 'Insurance product catalog used by policies, claims, quotes, and future offer logic.';

CREATE TABLE IF NOT EXISTS retainflow.silver.dim_customer (
  customer_id STRING COMMENT 'Stable synthetic customer identifier.',
  source_customer_id STRING,
  first_name STRING,
  last_name STRING,
  birth_date DATE,
  gender STRING,
  email STRING,
  phone STRING,
  geography_id STRING COMMENT 'Logical FK to dim_geography.geography_id.',
  acquisition_date DATE,
  acquisition_channel_id STRING COMMENT 'Logical FK to dim_channel.channel_id.',
  preferred_channel_id STRING COMMENT 'Logical FK to dim_channel.channel_id.',
  employment_status STRING,
  household_size INT,
  estimated_income_band STRING COMMENT 'LOW, LOWER_MID, MID, UPPER_MID, or HIGH.',
  digital_profile STRING COMMENT 'LOW, MEDIUM, or HIGH.',
  consent_email BOOLEAN,
  consent_sms BOOLEAN,
  consent_phone BOOLEAN,
  customer_segment STRING COMMENT 'PRICE_SENSITIVE, DIGITAL_FIRST, FAMILY_PROTECTOR, HIGH_VALUE, or LOW_ENGAGEMENT.',
  risk_affinity_score DOUBLE,
  price_sensitivity_score DOUBLE,
  service_sensitivity_score DOUBLE,
  digital_engagement_score DOUBLE,
  loyalty_score DOUBLE,
  claim_propensity_score DOUBLE,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
)
USING DELTA
COMMENT 'Clean customer master with demographics, consent, segmentation, and latent behavior drivers.';

CREATE TABLE IF NOT EXISTS retainflow.silver.fact_policy (
  policy_id STRING COMMENT 'Stable synthetic policy identifier.',
  source_policy_id STRING,
  customer_id STRING COMMENT 'Logical FK to dim_customer.customer_id.',
  product_id STRING COMMENT 'Logical FK to dim_product.product_id.',
  sales_channel_id STRING COMMENT 'Logical FK to dim_channel.channel_id.',
  agent_id STRING COMMENT 'Logical FK to dim_agent.agent_id.',
  policy_start_date DATE,
  policy_end_date DATE,
  next_renewal_date DATE,
  policy_status STRING COMMENT 'ACTIVE, LAPSED, CANCELLED, or EXPIRED.',
  payment_frequency STRING COMMENT 'MONTHLY, QUARTERLY, or ANNUAL.',
  annual_premium DECIMAL(12,2),
  premium_discount_pct DOUBLE,
  premium_increase_pct_last_renewal DOUBLE,
  cancellation_date DATE,
  cancellation_reason STRING,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
)
USING DELTA
COMMENT 'Insurance contracts held by customers, including premium, renewal, cancellation, and policy status.';

CREATE TABLE IF NOT EXISTS retainflow.silver.fact_policy_events (
  policy_event_id STRING COMMENT 'Stable policy lifecycle event identifier.',
  policy_id STRING COMMENT 'Logical FK to fact_policy.policy_id.',
  customer_id STRING COMMENT 'Logical FK to dim_customer.customer_id.',
  product_id STRING COMMENT 'Logical FK to dim_product.product_id.',
  event_date DATE,
  event_timestamp TIMESTAMP,
  event_type STRING COMMENT 'SUBSCRIPTION, RENEWAL, PREMIUM_CHANGE, ENDORSEMENT, CANCELLATION, REINSTATEMENT.',
  event_reason STRING,
  previous_policy_status STRING,
  new_policy_status STRING,
  previous_annual_premium DECIMAL(12,2),
  new_annual_premium DECIMAL(12,2),
  premium_change_pct DOUBLE,
  source_system STRING,
  created_at TIMESTAMP
)
USING DELTA
COMMENT 'Policy lifecycle events used to reconstruct renewals, premium changes, endorsements, and churn.';

CREATE TABLE IF NOT EXISTS retainflow.silver.fact_claims (
  claim_id STRING COMMENT 'Stable claim identifier.',
  source_claim_id STRING,
  policy_id STRING COMMENT 'Logical FK to fact_policy.policy_id.',
  customer_id STRING COMMENT 'Logical FK to dim_customer.customer_id.',
  product_id STRING COMMENT 'Logical FK to dim_product.product_id.',
  claim_date DATE,
  reported_date DATE,
  closed_date DATE,
  claim_type STRING,
  claim_status STRING COMMENT 'OPEN, UNDER_REVIEW, APPROVED, REJECTED, or CLOSED.',
  claim_amount DECIMAL(14,2),
  paid_amount DECIMAL(14,2),
  deductible_amount DECIMAL(12,2),
  handling_days INT,
  fraud_suspicion_flag BOOLEAN,
  claim_satisfaction_score DOUBLE,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
)
USING DELTA
COMMENT 'Insurance claims, settlement amounts, handling times, and satisfaction impact.';

CREATE TABLE IF NOT EXISTS retainflow.silver.fact_payments (
  payment_id STRING COMMENT 'Stable expected payment installment identifier.',
  policy_id STRING COMMENT 'Logical FK to fact_policy.policy_id.',
  customer_id STRING COMMENT 'Logical FK to dim_customer.customer_id.',
  due_date DATE,
  payment_date DATE,
  payment_year INT,
  payment_amount DECIMAL(12,2),
  payment_status STRING COMMENT 'PAID, LATE, REJECTED, REFUNDED, or WRITTEN_OFF.',
  payment_method STRING COMMENT 'CARD, DIRECT_DEBIT, BANK_TRANSFER, CHECK, CASH, or WALLET.',
  days_late INT,
  rejection_reason STRING,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
)
USING DELTA
COMMENT 'Expected and actual premium payments with delays, rejections, refunds, and write-offs.';

CREATE TABLE IF NOT EXISTS retainflow.silver.fact_interactions (
  interaction_id STRING COMMENT 'Stable customer touchpoint identifier.',
  customer_id STRING COMMENT 'Logical FK to dim_customer.customer_id.',
  policy_id STRING COMMENT 'Nullable logical FK to fact_policy.policy_id.',
  channel_id STRING COMMENT 'Logical FK to dim_channel.channel_id.',
  agent_id STRING COMMENT 'Nullable logical FK to dim_agent.agent_id.',
  interaction_datetime TIMESTAMP,
  interaction_year INT,
  interaction_type STRING COMMENT 'CALL, EMAIL, WEB_VISIT, MOBILE_SESSION, BRANCH_MEETING, CHAT, SMS.',
  interaction_reason STRING COMMENT 'QUOTE, CLAIM, BILLING, COMPLAINT, RENEWAL, RETENTION, GENERAL_SERVICE.',
  direction STRING COMMENT 'INBOUND or OUTBOUND.',
  duration_seconds INT,
  sentiment_score DOUBLE,
  resolved_flag BOOLEAN,
  created_at TIMESTAMP
)
USING DELTA
COMMENT 'Customer touchpoints across digital, call-center, branch, campaign, and service channels.';

CREATE TABLE IF NOT EXISTS retainflow.silver.fact_customer_service (
  case_id STRING COMMENT 'Stable service case identifier.',
  customer_id STRING COMMENT 'Logical FK to dim_customer.customer_id.',
  policy_id STRING COMMENT 'Nullable logical FK to fact_policy.policy_id.',
  interaction_id STRING COMMENT 'Nullable logical FK to fact_interactions.interaction_id.',
  opened_datetime TIMESTAMP,
  closed_datetime TIMESTAMP,
  case_type STRING COMMENT 'REQUEST, COMPLAINT, CLAIM_SUPPORT, BILLING, CANCELLATION_INTENT.',
  priority STRING COMMENT 'LOW, MEDIUM, HIGH, or CRITICAL.',
  case_status STRING COMMENT 'OPEN, IN_PROGRESS, RESOLVED, ESCALATED, or CLOSED.',
  sla_breached_flag BOOLEAN,
  resolution_code STRING,
  satisfaction_score DOUBLE,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
)
USING DELTA
COMMENT 'Service requests, complaints, billing issues, SLA breaches, and cancellation-intent cases.';

CREATE TABLE IF NOT EXISTS retainflow.silver.fact_campaign_contact (
  campaign_contact_id STRING COMMENT 'Stable customer-campaign contact identifier.',
  campaign_id STRING,
  customer_id STRING COMMENT 'Logical FK to dim_customer.customer_id.',
  policy_id STRING COMMENT 'Nullable logical FK to fact_policy.policy_id.',
  channel_id STRING COMMENT 'Logical FK to dim_channel.channel_id.',
  campaign_type STRING COMMENT 'ACQUISITION, CROSS_SELL, UPSELL, RENEWAL, WINBACK, RETENTION.',
  campaign_name STRING,
  contact_datetime TIMESTAMP,
  contact_year INT,
  opened_flag BOOLEAN,
  clicked_flag BOOLEAN,
  responded_flag BOOLEAN,
  converted_flag BOOLEAN,
  offer_id STRING,
  created_at TIMESTAMP
)
USING DELTA
COMMENT 'Marketing and retention campaign contacts with engagement and conversion outcomes.';

CREATE TABLE IF NOT EXISTS retainflow.silver.fact_quotes (
  quote_id STRING COMMENT 'Stable quote identifier.',
  customer_id STRING COMMENT 'Logical FK to dim_customer.customer_id.',
  product_id STRING COMMENT 'Logical FK to dim_product.product_id.',
  channel_id STRING COMMENT 'Logical FK to dim_channel.channel_id.',
  agent_id STRING COMMENT 'Nullable logical FK to dim_agent.agent_id.',
  quote_date DATE,
  quoted_annual_premium DECIMAL(12,2),
  competitor_price_index DOUBLE COMMENT 'Synthetic competitor price pressure index. Lower means competitor is cheaper.',
  quote_status STRING COMMENT 'CREATED, SENT, ACCEPTED, DECLINED, or EXPIRED.',
  converted_policy_id STRING COMMENT 'Nullable logical FK to fact_policy.policy_id.',
  created_at TIMESTAMP,
  updated_at TIMESTAMP
)
USING DELTA
COMMENT 'Customer and campaign-triggered insurance quotes, acceptance behavior, and competitor pressure.';

CREATE TABLE IF NOT EXISTS retainflow.silver.fact_retention_actions (
  retention_action_id STRING COMMENT 'Stable retention action identifier.',
  customer_id STRING COMMENT 'Logical FK to dim_customer.customer_id.',
  policy_id STRING COMMENT 'Nullable logical FK to fact_policy.policy_id.',
  action_date DATE,
  action_timestamp TIMESTAMP,
  action_type STRING COMMENT 'DISCOUNT, COVERAGE_UPGRADE, CALLBACK, PAYMENT_PLAN, LOYALTY_BONUS, CLAIM_REVIEW.',
  trigger_reason STRING COMMENT 'PREMIUM_INCREASE, COMPLAINT, PAYMENT_INCIDENT, LOW_ENGAGEMENT, RENEWAL_RISK, HIGH_VALUE_SAVE.',
  offered_value DECIMAL(12,2),
  channel_id STRING COMMENT 'Logical FK to dim_channel.channel_id.',
  agent_id STRING COMMENT 'Nullable logical FK to dim_agent.agent_id.',
  accepted_flag BOOLEAN,
  retained_90d_flag BOOLEAN,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
)
USING DELTA
COMMENT 'Historical save actions and outcomes; later reused by retention agents and next-best-action logic.';

CREATE TABLE IF NOT EXISTS retainflow.gold.customer_360_snapshot (
  observation_date DATE COMMENT 'Feature observation date. No future information should be used beyond this date.',
  customer_id STRING COMMENT 'Logical FK to silver.dim_customer.customer_id.',
  tenure_months INT,
  active_policy_count INT,
  number_of_products INT,
  total_annual_premium DECIMAL(14,2),
  total_claims_12m INT,
  total_claim_amount_12m DECIMAL(14,2),
  payment_incidents_6m INT,
  complaints_6m INT,
  interactions_3m INT,
  days_since_last_contact INT,
  digital_sessions_30d INT,
  email_open_rate_6m DOUBLE,
  premium_increase_pct_max_12m DOUBLE,
  avg_satisfaction_score_12m DOUBLE,
  renewal_days_min INT,
  customer_value_score DOUBLE,
  latent_churn_risk_band STRING COMMENT 'LOW, MEDIUM, HIGH, or VERY_HIGH. Diagnostic synthetic signal, not final ML label.',
  created_at TIMESTAMP
)
USING DELTA
COMMENT 'Starter customer 360 snapshot for churn modeling, prioritization, and future agentic recommendations.';

CREATE TABLE IF NOT EXISTS retainflow.gold.retention_priority_queue (
  recommendation_id STRING COMMENT 'Stable recommendation identifier for the scoring run.',
  observation_date DATE COMMENT 'Feature observation date.',
  customer_id STRING COMMENT 'Recommended customer to prioritize.',
  churn_probability DOUBLE COMMENT 'Predicted churn probability.',
  churn_risk_band STRING COMMENT 'LOW, MEDIUM, HIGH, or VERY_HIGH.',
  priority_score DOUBLE COMMENT 'Business priority score combining churn risk and customer value.',
  priority_tier STRING COMMENT 'P1, P2, P3, or P4.',
  recommended_action_type STRING COMMENT 'DISCOUNT, CALLBACK, PAYMENT_PLAN, CLAIM_REVIEW, COVERAGE_UPGRADE, or LOYALTY_BONUS.',
  action_reason STRING COMMENT 'Business reason behind the recommendation.',
  recommended_channel_id STRING COMMENT 'Logical FK to silver.dim_channel.channel_id.',
  recommended_channel_name STRING,
  estimated_offer_value DECIMAL(12,2),
  customer_value_score DOUBLE,
  total_annual_premium DECIMAL(14,2),
  renewal_days_min INT,
  model_name STRING,
  scoring_run_id STRING,
  created_at TIMESTAMP
)
USING DELTA
COMMENT 'Prioritized retention recommendations built from churn scores and Customer 360 signals.';

CREATE TABLE IF NOT EXISTS retainflow.ml.churn_feature_snapshot (
  observation_date DATE COMMENT 'Feature observation date.',
  customer_id STRING COMMENT 'Logical FK to silver.dim_customer.customer_id.',
  tenure_months INT,
  active_policy_count INT,
  number_of_products INT,
  total_annual_premium DOUBLE,
  total_claims_12m INT,
  total_claim_amount_12m DOUBLE,
  payment_incidents_6m INT,
  complaints_6m INT,
  interactions_3m INT,
  days_since_last_contact INT,
  digital_sessions_30d INT,
  email_open_rate_6m DOUBLE,
  premium_increase_pct_max_12m DOUBLE,
  avg_satisfaction_score_12m DOUBLE,
  renewal_days_min INT,
  customer_value_score DOUBLE,
  customer_segment STRING,
  estimated_income_band STRING,
  digital_profile STRING,
  price_sensitivity_score DOUBLE,
  digital_engagement_score DOUBLE,
  loyalty_score DOUBLE,
  created_at TIMESTAMP
)
USING DELTA
COMMENT 'ML-ready churn feature snapshot built without using post-observation future information.';

CREATE TABLE IF NOT EXISTS retainflow.ml.churn_labels (
  observation_date DATE COMMENT 'Feature observation date.',
  customer_id STRING COMMENT 'Logical FK to silver.dim_customer.customer_id.',
  prediction_horizon_days INT,
  churn_label INT COMMENT '1 if customer churns in the prediction horizon, else 0.',
  churn_probability DOUBLE COMMENT 'Synthetic churn probability generated from business signals.',
  churn_risk_band STRING COMMENT 'LOW, MEDIUM, HIGH, or VERY_HIGH.',
  label_reason STRING COMMENT 'Dominant synthetic churn driver.',
  created_at TIMESTAMP
)
USING DELTA
COMMENT 'Synthetic churn labels for future supervised ML experiments.';

CREATE TABLE IF NOT EXISTS retainflow.ml.churn_predictions (
  observation_date DATE COMMENT 'Feature observation date.',
  customer_id STRING COMMENT 'Scored customer identifier.',
  churn_probability DOUBLE COMMENT 'Predicted probability of churn.',
  predicted_churn_label INT COMMENT 'Predicted churn class from the configured threshold.',
  churn_risk_band STRING COMMENT 'LOW, MEDIUM, HIGH, or VERY_HIGH.',
  model_name STRING,
  model_version STRING,
  scoring_run_id STRING,
  scored_at TIMESTAMP
)
USING DELTA
COMMENT 'Batch churn scores generated by the churn model pipeline.';

CREATE TABLE IF NOT EXISTS retainflow.monitoring.generation_batches (
  batch_id STRING COMMENT 'Synthetic generation batch identifier.',
  run_started_at TIMESTAMP,
  run_finished_at TIMESTAMP,
  generation_mode STRING COMMENT 'reset or incremental.',
  seed INT,
  n_customers INT,
  history_start_date DATE,
  history_end_date DATE,
  status STRING COMMENT 'STARTED, SUCCEEDED, FAILED.',
  error_message STRING,
  created_by STRING
)
USING DELTA
COMMENT 'Audit table for synthetic data generation runs.';

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

CREATE TABLE IF NOT EXISTS retainflow.monitoring.data_quality_results (
  dq_result_id STRING COMMENT 'Stable data quality result identifier.',
  batch_id STRING COMMENT 'Logical FK to monitoring.generation_batches.batch_id.',
  catalog_name STRING,
  schema_name STRING,
  table_name STRING,
  check_name STRING,
  check_type STRING COMMENT 'PK_UNIQUENESS, FK_ORPHAN, ENUM_VALIDITY, RANGE, NULL_RATE, DUPLICATE, DISTRIBUTION.',
  check_status STRING COMMENT 'PASS, WARN, or FAIL.',
  observed_value DOUBLE,
  expected_value DOUBLE,
  threshold_value DOUBLE,
  failed_row_count BIGINT,
  check_message STRING,
  checked_at TIMESTAMP
)
USING DELTA
COMMENT 'Data quality control results for primary keys, logical foreign keys, enums, date ranges, and distributions.';

CREATE TABLE IF NOT EXISTS retainflow.monitoring.logical_relationships (
  relationship_id STRING COMMENT 'Stable relationship identifier.',
  child_catalog STRING,
  child_schema STRING,
  child_table STRING,
  child_columns ARRAY<STRING>,
  parent_catalog STRING,
  parent_schema STRING,
  parent_table STRING,
  parent_columns ARRAY<STRING>,
  relationship_type STRING COMMENT 'MANY_TO_ONE, ONE_TO_MANY, or OPTIONAL_MANY_TO_ONE.',
  is_required BOOLEAN,
  description STRING
)
USING DELTA
COMMENT 'Documented logical relationships used by generators, DQ checks, and future agent SQL context.';

DELETE FROM retainflow.monitoring.logical_relationships;

INSERT INTO retainflow.monitoring.logical_relationships
SELECT *
FROM VALUES
  ('rel_customer_geography', 'retainflow', 'silver', 'dim_customer', array('geography_id'), 'retainflow', 'silver', 'dim_geography', array('geography_id'), 'MANY_TO_ONE', true, 'Customer location.'),
  ('rel_customer_acquisition_channel', 'retainflow', 'silver', 'dim_customer', array('acquisition_channel_id'), 'retainflow', 'silver', 'dim_channel', array('channel_id'), 'MANY_TO_ONE', true, 'Customer acquisition channel.'),
  ('rel_customer_preferred_channel', 'retainflow', 'silver', 'dim_customer', array('preferred_channel_id'), 'retainflow', 'silver', 'dim_channel', array('channel_id'), 'MANY_TO_ONE', true, 'Customer preferred contact channel.'),
  ('rel_agent_channel', 'retainflow', 'silver', 'dim_agent', array('channel_id'), 'retainflow', 'silver', 'dim_channel', array('channel_id'), 'MANY_TO_ONE', true, 'Agent primary channel.'),
  ('rel_agent_geography', 'retainflow', 'silver', 'dim_agent', array('geography_id'), 'retainflow', 'silver', 'dim_geography', array('geography_id'), 'MANY_TO_ONE', true, 'Agent geography.'),
  ('rel_policy_customer', 'retainflow', 'silver', 'fact_policy', array('customer_id'), 'retainflow', 'silver', 'dim_customer', array('customer_id'), 'MANY_TO_ONE', true, 'Policy holder.'),
  ('rel_policy_product', 'retainflow', 'silver', 'fact_policy', array('product_id'), 'retainflow', 'silver', 'dim_product', array('product_id'), 'MANY_TO_ONE', true, 'Policy product.'),
  ('rel_policy_sales_channel', 'retainflow', 'silver', 'fact_policy', array('sales_channel_id'), 'retainflow', 'silver', 'dim_channel', array('channel_id'), 'MANY_TO_ONE', true, 'Policy sales channel.'),
  ('rel_policy_agent', 'retainflow', 'silver', 'fact_policy', array('agent_id'), 'retainflow', 'silver', 'dim_agent', array('agent_id'), 'OPTIONAL_MANY_TO_ONE', false, 'Policy selling agent.'),
  ('rel_policy_event_policy', 'retainflow', 'silver', 'fact_policy_events', array('policy_id'), 'retainflow', 'silver', 'fact_policy', array('policy_id'), 'MANY_TO_ONE', true, 'Policy event parent policy.'),
  ('rel_claim_policy', 'retainflow', 'silver', 'fact_claims', array('policy_id'), 'retainflow', 'silver', 'fact_policy', array('policy_id'), 'MANY_TO_ONE', true, 'Claim parent policy.'),
  ('rel_payment_policy', 'retainflow', 'silver', 'fact_payments', array('policy_id'), 'retainflow', 'silver', 'fact_policy', array('policy_id'), 'MANY_TO_ONE', true, 'Payment parent policy.'),
  ('rel_interaction_customer', 'retainflow', 'silver', 'fact_interactions', array('customer_id'), 'retainflow', 'silver', 'dim_customer', array('customer_id'), 'MANY_TO_ONE', true, 'Customer interaction owner.'),
  ('rel_service_customer', 'retainflow', 'silver', 'fact_customer_service', array('customer_id'), 'retainflow', 'silver', 'dim_customer', array('customer_id'), 'MANY_TO_ONE', true, 'Service case customer.'),
  ('rel_campaign_customer', 'retainflow', 'silver', 'fact_campaign_contact', array('customer_id'), 'retainflow', 'silver', 'dim_customer', array('customer_id'), 'MANY_TO_ONE', true, 'Campaign contact recipient.'),
  ('rel_quote_customer', 'retainflow', 'silver', 'fact_quotes', array('customer_id'), 'retainflow', 'silver', 'dim_customer', array('customer_id'), 'MANY_TO_ONE', true, 'Quote customer.'),
  ('rel_retention_customer', 'retainflow', 'silver', 'fact_retention_actions', array('customer_id'), 'retainflow', 'silver', 'dim_customer', array('customer_id'), 'MANY_TO_ONE', true, 'Retention action target customer.'),
  ('rel_customer360_customer', 'retainflow', 'gold', 'customer_360_snapshot', array('customer_id'), 'retainflow', 'silver', 'dim_customer', array('customer_id'), 'MANY_TO_ONE', true, 'Customer 360 parent customer.')
AS rel(
  relationship_id,
  child_catalog,
  child_schema,
  child_table,
  child_columns,
  parent_catalog,
  parent_schema,
  parent_table,
  parent_columns,
  relationship_type,
  is_required,
  description
);
