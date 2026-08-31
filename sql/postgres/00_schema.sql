CREATE SCHEMA IF NOT EXISTS retainflow;

CREATE TABLE IF NOT EXISTS retainflow.dim_date (
  date_key integer PRIMARY KEY,
  calendar_date date NOT NULL UNIQUE,
  calendar_year integer NOT NULL,
  calendar_quarter integer NOT NULL,
  calendar_month integer NOT NULL,
  month_name text NOT NULL,
  day_of_month integer NOT NULL,
  day_of_week integer NOT NULL,
  week_of_year integer NOT NULL,
  is_weekend boolean NOT NULL,
  is_month_end boolean NOT NULL,
  is_quarter_end boolean NOT NULL,
  is_year_end boolean NOT NULL
);

CREATE TABLE IF NOT EXISTS retainflow.dim_geography (
  geography_id text PRIMARY KEY,
  country text NOT NULL DEFAULT 'FR',
  region text NOT NULL,
  department text NOT NULL,
  city text NOT NULL,
  postal_code text NOT NULL,
  urbanicity text NOT NULL CHECK (urbanicity IN ('URBAN', 'SUBURBAN', 'RURAL')),
  income_index numeric(5,2) NOT NULL,
  claim_risk_index numeric(5,2) NOT NULL,
  digital_adoption_index numeric(5,2) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS retainflow.dim_agency (
  agency_id text PRIMARY KEY,
  agency_code text NOT NULL UNIQUE,
  agency_name text NOT NULL,
  geography_id text NOT NULL REFERENCES retainflow.dim_geography(geography_id),
  agency_type text NOT NULL CHECK (agency_type IN ('BRANCH', 'CALL_CENTER', 'BROKER_HUB', 'RETENTION_CENTER')),
  opened_date date NOT NULL,
  employee_count integer NOT NULL CHECK (employee_count > 0),
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS retainflow.dim_channel (
  channel_id text PRIMARY KEY,
  channel_code text NOT NULL UNIQUE,
  channel_name text NOT NULL,
  channel_family text NOT NULL CHECK (channel_family IN ('DIGITAL', 'HUMAN', 'PARTNER', 'OUTBOUND')),
  is_digital boolean NOT NULL,
  is_inbound boolean NOT NULL,
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS retainflow.dim_agent (
  agent_id text PRIMARY KEY,
  source_agent_id text NOT NULL UNIQUE,
  agent_name text NOT NULL,
  agent_role text NOT NULL CHECK (agent_role IN ('SALES', 'SERVICE', 'CLAIMS', 'RETENTION', 'HYBRID')),
  channel_id text NOT NULL REFERENCES retainflow.dim_channel(channel_id),
  agency_id text NOT NULL REFERENCES retainflow.dim_agency(agency_id),
  team_name text NOT NULL,
  hire_date date NOT NULL,
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS retainflow.dim_product (
  product_id text PRIMARY KEY,
  product_family text NOT NULL CHECK (product_family IN ('AUTO', 'HOME', 'HEALTH', 'LIFE', 'TRAVEL', 'PET', 'PERSONAL_ACCIDENT')),
  product_name text NOT NULL,
  coverage_tier text NOT NULL CHECK (coverage_tier IN ('BASIC', 'STANDARD', 'PREMIUM')),
  base_annual_premium numeric(12,2) NOT NULL,
  deductible_amount numeric(12,2) NOT NULL,
  risk_level text NOT NULL CHECK (risk_level IN ('LOW', 'MEDIUM', 'HIGH', 'VERY_HIGH')),
  default_payment_frequency text NOT NULL CHECK (default_payment_frequency IN ('MONTHLY', 'QUARTERLY', 'ANNUAL')),
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS retainflow.dim_customer (
  customer_id text PRIMARY KEY,
  source_customer_id text NOT NULL UNIQUE,
  first_name text NOT NULL,
  last_name text NOT NULL,
  birth_date date NOT NULL,
  gender text NOT NULL CHECK (gender IN ('F', 'M', 'OTHER')),
  email text NOT NULL UNIQUE,
  phone text,
  geography_id text NOT NULL REFERENCES retainflow.dim_geography(geography_id),
  home_agency_id text NOT NULL REFERENCES retainflow.dim_agency(agency_id),
  acquisition_date date NOT NULL,
  acquisition_channel_id text NOT NULL REFERENCES retainflow.dim_channel(channel_id),
  preferred_channel_id text NOT NULL REFERENCES retainflow.dim_channel(channel_id),
  employment_status text NOT NULL,
  household_size integer NOT NULL CHECK (household_size BETWEEN 1 AND 7),
  estimated_income_band text NOT NULL CHECK (estimated_income_band IN ('LOW', 'LOWER_MID', 'MID', 'UPPER_MID', 'HIGH')),
  digital_profile text NOT NULL CHECK (digital_profile IN ('LOW', 'MEDIUM', 'HIGH')),
  consent_email boolean NOT NULL,
  consent_sms boolean NOT NULL,
  consent_phone boolean NOT NULL,
  customer_segment text NOT NULL CHECK (customer_segment IN ('PRICE_SENSITIVE', 'DIGITAL_FIRST', 'FAMILY_PROTECTOR', 'HIGH_VALUE', 'LOW_ENGAGEMENT')),
  risk_affinity_score numeric(6,4) NOT NULL,
  price_sensitivity_score numeric(6,4) NOT NULL,
  service_sensitivity_score numeric(6,4) NOT NULL,
  digital_engagement_score numeric(6,4) NOT NULL,
  loyalty_score numeric(6,4) NOT NULL,
  claim_propensity_score numeric(6,4) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS retainflow.fact_policy (
  policy_id text PRIMARY KEY,
  source_policy_id text NOT NULL UNIQUE,
  customer_id text NOT NULL REFERENCES retainflow.dim_customer(customer_id),
  product_id text NOT NULL REFERENCES retainflow.dim_product(product_id),
  sales_channel_id text NOT NULL REFERENCES retainflow.dim_channel(channel_id),
  agent_id text REFERENCES retainflow.dim_agent(agent_id),
  agency_id text NOT NULL REFERENCES retainflow.dim_agency(agency_id),
  policy_start_date date NOT NULL,
  policy_end_date date NOT NULL,
  next_renewal_date date,
  policy_status text NOT NULL CHECK (policy_status IN ('ACTIVE', 'LAPSED', 'CANCELLED', 'EXPIRED')),
  payment_frequency text NOT NULL CHECK (payment_frequency IN ('MONTHLY', 'QUARTERLY', 'ANNUAL')),
  annual_premium numeric(12,2) NOT NULL,
  premium_discount_pct numeric(6,4) NOT NULL,
  premium_increase_pct_last_renewal numeric(6,4) NOT NULL,
  cancellation_date date,
  cancellation_reason text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT cancellation_consistency CHECK (
    (policy_status IN ('CANCELLED', 'LAPSED') AND cancellation_date IS NOT NULL)
    OR (policy_status NOT IN ('CANCELLED', 'LAPSED') AND cancellation_date IS NULL)
  )
);

CREATE TABLE IF NOT EXISTS retainflow.fact_policy_event (
  policy_event_id text PRIMARY KEY,
  policy_id text NOT NULL REFERENCES retainflow.fact_policy(policy_id),
  customer_id text NOT NULL REFERENCES retainflow.dim_customer(customer_id),
  product_id text NOT NULL REFERENCES retainflow.dim_product(product_id),
  event_date date NOT NULL,
  event_timestamp timestamptz NOT NULL,
  event_type text NOT NULL CHECK (event_type IN ('SUBSCRIPTION', 'RENEWAL', 'PREMIUM_CHANGE', 'ENDORSEMENT', 'CANCELLATION', 'REINSTATEMENT')),
  event_reason text,
  previous_policy_status text,
  new_policy_status text,
  previous_annual_premium numeric(12,2),
  new_annual_premium numeric(12,2),
  premium_change_pct numeric(6,4),
  source_system text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS retainflow.fact_payment (
  payment_id text PRIMARY KEY,
  policy_id text NOT NULL REFERENCES retainflow.fact_policy(policy_id),
  customer_id text NOT NULL REFERENCES retainflow.dim_customer(customer_id),
  due_date date NOT NULL,
  payment_date date,
  payment_year integer NOT NULL,
  payment_amount numeric(12,2) NOT NULL,
  payment_status text NOT NULL CHECK (payment_status IN ('PAID', 'LATE', 'REJECTED', 'REFUNDED', 'WRITTEN_OFF')),
  payment_method text NOT NULL CHECK (payment_method IN ('CARD', 'DIRECT_DEBIT', 'BANK_TRANSFER', 'CHECK', 'CASH', 'WALLET')),
  days_late integer NOT NULL DEFAULT 0,
  rejection_reason text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS retainflow.fact_claim (
  claim_id text PRIMARY KEY,
  source_claim_id text NOT NULL UNIQUE,
  policy_id text NOT NULL REFERENCES retainflow.fact_policy(policy_id),
  customer_id text NOT NULL REFERENCES retainflow.dim_customer(customer_id),
  product_id text NOT NULL REFERENCES retainflow.dim_product(product_id),
  claim_date date NOT NULL,
  reported_date date NOT NULL,
  closed_date date,
  claim_type text NOT NULL,
  claim_status text NOT NULL CHECK (claim_status IN ('OPEN', 'UNDER_REVIEW', 'APPROVED', 'REJECTED', 'CLOSED')),
  claim_amount numeric(14,2) NOT NULL,
  paid_amount numeric(14,2) NOT NULL,
  deductible_amount numeric(12,2) NOT NULL,
  handling_days integer,
  fraud_suspicion_flag boolean NOT NULL,
  claim_satisfaction_score numeric(4,2),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS retainflow.fact_interaction (
  interaction_id text PRIMARY KEY,
  customer_id text NOT NULL REFERENCES retainflow.dim_customer(customer_id),
  policy_id text REFERENCES retainflow.fact_policy(policy_id),
  channel_id text NOT NULL REFERENCES retainflow.dim_channel(channel_id),
  agent_id text REFERENCES retainflow.dim_agent(agent_id),
  interaction_datetime timestamptz NOT NULL,
  interaction_year integer NOT NULL,
  interaction_type text NOT NULL,
  interaction_reason text NOT NULL,
  direction text NOT NULL CHECK (direction IN ('INBOUND', 'OUTBOUND')),
  duration_seconds integer NOT NULL,
  sentiment_score numeric(5,3) NOT NULL,
  resolved_flag boolean NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS retainflow.fact_customer_service (
  case_id text PRIMARY KEY,
  customer_id text NOT NULL REFERENCES retainflow.dim_customer(customer_id),
  policy_id text REFERENCES retainflow.fact_policy(policy_id),
  interaction_id text REFERENCES retainflow.fact_interaction(interaction_id),
  opened_datetime timestamptz NOT NULL,
  closed_datetime timestamptz,
  case_type text NOT NULL CHECK (case_type IN ('REQUEST', 'COMPLAINT', 'CLAIM_SUPPORT', 'BILLING', 'CANCELLATION_INTENT')),
  priority text NOT NULL CHECK (priority IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
  case_status text NOT NULL CHECK (case_status IN ('OPEN', 'IN_PROGRESS', 'RESOLVED', 'ESCALATED', 'CLOSED')),
  sla_breached_flag boolean NOT NULL,
  resolution_code text,
  satisfaction_score numeric(4,2),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS retainflow.fact_campaign_contact (
  campaign_contact_id text PRIMARY KEY,
  campaign_id text NOT NULL,
  customer_id text NOT NULL REFERENCES retainflow.dim_customer(customer_id),
  policy_id text REFERENCES retainflow.fact_policy(policy_id),
  channel_id text NOT NULL REFERENCES retainflow.dim_channel(channel_id),
  campaign_type text NOT NULL CHECK (campaign_type IN ('ACQUISITION', 'CROSS_SELL', 'UPSELL', 'RENEWAL', 'WINBACK', 'RETENTION')),
  campaign_name text NOT NULL,
  contact_datetime timestamptz NOT NULL,
  contact_year integer NOT NULL,
  opened_flag boolean NOT NULL,
  clicked_flag boolean NOT NULL,
  responded_flag boolean NOT NULL,
  converted_flag boolean NOT NULL,
  offer_id text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS retainflow.fact_quote (
  quote_id text PRIMARY KEY,
  customer_id text NOT NULL REFERENCES retainflow.dim_customer(customer_id),
  product_id text NOT NULL REFERENCES retainflow.dim_product(product_id),
  channel_id text NOT NULL REFERENCES retainflow.dim_channel(channel_id),
  agent_id text REFERENCES retainflow.dim_agent(agent_id),
  quote_date date NOT NULL,
  quoted_annual_premium numeric(12,2) NOT NULL,
  competitor_price_index numeric(6,4) NOT NULL,
  quote_status text NOT NULL CHECK (quote_status IN ('CREATED', 'SENT', 'ACCEPTED', 'DECLINED', 'EXPIRED')),
  converted_policy_id text REFERENCES retainflow.fact_policy(policy_id),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS retainflow.fact_retention_action (
  retention_action_id text PRIMARY KEY,
  customer_id text NOT NULL REFERENCES retainflow.dim_customer(customer_id),
  policy_id text REFERENCES retainflow.fact_policy(policy_id),
  action_date date NOT NULL,
  action_timestamp timestamptz NOT NULL,
  action_type text NOT NULL CHECK (action_type IN ('DISCOUNT', 'COVERAGE_UPGRADE', 'CALLBACK', 'PAYMENT_PLAN', 'LOYALTY_BONUS', 'CLAIM_REVIEW')),
  trigger_reason text NOT NULL CHECK (trigger_reason IN ('PREMIUM_INCREASE', 'COMPLAINT', 'PAYMENT_INCIDENT', 'LOW_ENGAGEMENT', 'RENEWAL_RISK', 'HIGH_VALUE_SAVE')),
  offered_value numeric(12,2) NOT NULL,
  channel_id text NOT NULL REFERENCES retainflow.dim_channel(channel_id),
  agent_id text REFERENCES retainflow.dim_agent(agent_id),
  accepted_flag boolean NOT NULL,
  retained_90d_flag boolean NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS retainflow.customer_360_snapshot (
  observation_date date NOT NULL,
  customer_id text NOT NULL REFERENCES retainflow.dim_customer(customer_id),
  split_name text NOT NULL CHECK (split_name IN ('train', 'validation', 'test', 'backtest')),
  tenure_months integer NOT NULL,
  active_policy_count integer NOT NULL,
  number_of_products integer NOT NULL,
  total_annual_premium numeric(14,2) NOT NULL,
  total_claims_12m integer NOT NULL,
  total_claim_amount_12m numeric(14,2) NOT NULL,
  payment_incidents_6m integer NOT NULL,
  complaints_6m integer NOT NULL,
  interactions_3m integer NOT NULL,
  days_since_last_contact integer NOT NULL,
  digital_sessions_30d integer NOT NULL,
  email_open_rate_6m numeric(6,4) NOT NULL,
  premium_increase_pct_max_12m numeric(6,4) NOT NULL,
  avg_satisfaction_score_12m numeric(4,2),
  renewal_days_min integer,
  customer_value_score numeric(8,4) NOT NULL,
  customer_age_years numeric(5,2) NOT NULL,
  active_auto_policy_count integer NOT NULL,
  active_home_policy_count integer NOT NULL,
  active_health_policy_count integer NOT NULL,
  active_life_policy_count integer NOT NULL,
  cancelled_policy_count_to_date integer NOT NULL,
  policy_age_avg_months numeric(8,2) NOT NULL,
  late_payment_count_12m integer NOT NULL,
  rejected_payment_count_12m integer NOT NULL,
  service_case_count_12m integer NOT NULL,
  unresolved_case_count_12m integer NOT NULL,
  retention_offer_count_12m integer NOT NULL,
  retention_acceptance_rate_12m numeric(6,4) NOT NULL,
  quote_count_6m integer NOT NULL,
  competitor_price_index_avg_6m numeric(6,4) NOT NULL,
  campaign_response_rate_6m numeric(6,4) NOT NULL,
  main_product_family text NOT NULL,
  highest_coverage_tier text NOT NULL,
  latent_churn_risk_band text NOT NULL CHECK (latent_churn_risk_band IN ('LOW', 'MEDIUM', 'HIGH', 'VERY_HIGH')),
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (observation_date, customer_id)
);

CREATE TABLE IF NOT EXISTS retainflow.churn_label (
  observation_date date NOT NULL,
  customer_id text NOT NULL REFERENCES retainflow.dim_customer(customer_id),
  split_name text NOT NULL CHECK (split_name IN ('train', 'validation', 'test', 'backtest')),
  prediction_horizon_days integer NOT NULL,
  churn_label integer NOT NULL CHECK (churn_label IN (0, 1)),
  churn_date date,
  customer_lifecycle_status text NOT NULL CHECK (customer_lifecycle_status IN ('ACTIVE_OBSERVED', 'CHURNED_WITHIN_HORIZON')),
  churn_probability numeric(6,4) NOT NULL,
  churn_risk_band text NOT NULL CHECK (churn_risk_band IN ('LOW', 'MEDIUM', 'HIGH', 'VERY_HIGH')),
  label_reason text NOT NULL,
  CONSTRAINT churn_label_date_consistency CHECK (
    (churn_label = 1 AND churn_date IS NOT NULL AND customer_lifecycle_status = 'CHURNED_WITHIN_HORIZON')
    OR (churn_label = 0 AND churn_date IS NULL AND customer_lifecycle_status = 'ACTIVE_OBSERVED')
  ),
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (observation_date, customer_id)
);

ALTER TABLE retainflow.churn_label
  ADD COLUMN IF NOT EXISTS churn_date date;

ALTER TABLE retainflow.churn_label
  ADD COLUMN IF NOT EXISTS customer_lifecycle_status text;

UPDATE retainflow.churn_label
SET churn_date = observation_date + prediction_horizon_days
WHERE churn_label = 1
  AND churn_date IS NULL;

UPDATE retainflow.churn_label
SET customer_lifecycle_status = CASE
  WHEN churn_label = 1 THEN 'CHURNED_WITHIN_HORIZON'
  ELSE 'ACTIVE_OBSERVED'
END
WHERE customer_lifecycle_status IS NULL;

ALTER TABLE retainflow.churn_label
  ALTER COLUMN customer_lifecycle_status SET NOT NULL;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'churn_label_lifecycle_status_check'
      AND conrelid = 'retainflow.churn_label'::regclass
  ) THEN
    ALTER TABLE retainflow.churn_label
      ADD CONSTRAINT churn_label_lifecycle_status_check
      CHECK (customer_lifecycle_status IN ('ACTIVE_OBSERVED', 'CHURNED_WITHIN_HORIZON'));
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'churn_label_date_consistency'
      AND conrelid = 'retainflow.churn_label'::regclass
  ) THEN
    ALTER TABLE retainflow.churn_label
      ADD CONSTRAINT churn_label_date_consistency CHECK (
        (churn_label = 1 AND churn_date IS NOT NULL AND customer_lifecycle_status = 'CHURNED_WITHIN_HORIZON')
        OR (churn_label = 0 AND churn_date IS NULL AND customer_lifecycle_status = 'ACTIVE_OBSERVED')
      );
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS retainflow.churn_prediction (
  observation_date date NOT NULL,
  customer_id text NOT NULL REFERENCES retainflow.dim_customer(customer_id),
  split_name text NOT NULL CHECK (split_name IN ('validation', 'test', 'backtest', 'scoring')),
  churn_probability numeric(8,6) NOT NULL,
  predicted_churn_label integer NOT NULL CHECK (predicted_churn_label IN (0, 1)),
  churn_risk_band text NOT NULL CHECK (churn_risk_band IN ('LOW', 'MEDIUM', 'HIGH', 'VERY_HIGH')),
  model_name text NOT NULL,
  model_version text,
  mlflow_run_id text NOT NULL,
  scored_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (observation_date, customer_id, model_name, mlflow_run_id)
);

CREATE TABLE IF NOT EXISTS retainflow.generation_batch (
  batch_id text PRIMARY KEY,
  run_started_at timestamptz NOT NULL,
  run_finished_at timestamptz,
  generation_mode text NOT NULL CHECK (generation_mode IN ('reset', 'incremental')),
  seed integer NOT NULL,
  n_customers integer NOT NULL,
  history_start_date date NOT NULL,
  history_end_date date NOT NULL,
  status text NOT NULL CHECK (status IN ('STARTED', 'SUCCEEDED', 'FAILED')),
  error_message text,
  created_by text NOT NULL DEFAULT current_user
);

CREATE INDEX IF NOT EXISTS idx_customer_geo ON retainflow.dim_customer(geography_id);
CREATE INDEX IF NOT EXISTS idx_customer_agency ON retainflow.dim_customer(home_agency_id);
CREATE INDEX IF NOT EXISTS idx_policy_customer ON retainflow.fact_policy(customer_id);
CREATE INDEX IF NOT EXISTS idx_policy_status ON retainflow.fact_policy(policy_status);
CREATE INDEX IF NOT EXISTS idx_payment_customer_due ON retainflow.fact_payment(customer_id, due_date);
CREATE INDEX IF NOT EXISTS idx_claim_customer_date ON retainflow.fact_claim(customer_id, claim_date);
CREATE INDEX IF NOT EXISTS idx_interaction_customer_date ON retainflow.fact_interaction(customer_id, interaction_datetime);
CREATE INDEX IF NOT EXISTS idx_service_customer_opened ON retainflow.fact_customer_service(customer_id, opened_datetime);
CREATE INDEX IF NOT EXISTS idx_campaign_customer_contact ON retainflow.fact_campaign_contact(customer_id, contact_datetime);
CREATE INDEX IF NOT EXISTS idx_quote_customer_date ON retainflow.fact_quote(customer_id, quote_date);
CREATE INDEX IF NOT EXISTS idx_retention_customer_date ON retainflow.fact_retention_action(customer_id, action_date);
CREATE INDEX IF NOT EXISTS idx_snapshot_split ON retainflow.customer_360_snapshot(split_name, observation_date);
CREATE INDEX IF NOT EXISTS idx_label_split ON retainflow.churn_label(split_name, observation_date);
CREATE INDEX IF NOT EXISTS idx_prediction_split ON retainflow.churn_prediction(split_name, observation_date);

COMMENT ON SCHEMA retainflow IS 'RetainFlow PostgreSQL source system for French insurance retention data.';
COMMENT ON TABLE retainflow.dim_agency IS 'French insurance agencies and operational hubs; the local substitute for Databricks-centric organizational context.';
COMMENT ON TABLE retainflow.customer_360_snapshot IS 'ML-ready customer features split into train, validation, test, and backtest windows.';
COMMENT ON TABLE retainflow.churn_label IS 'Synthetic churn labels generated from business signals for supervised learning and later SHAP explainability.';
COMMENT ON TABLE retainflow.churn_prediction IS 'Local churn scores produced by the PostgreSQL and MLflow training pipeline.';
