-- RetainFlow - Phase 1 reference dimension seed data
-- Run after 00_define_uc_model.sql.

DELETE FROM retainflow.silver.dim_date;
DELETE FROM retainflow.silver.dim_channel;
DELETE FROM retainflow.silver.dim_product;
DELETE FROM retainflow.silver.dim_geography;
DELETE FROM retainflow.silver.dim_agent;

INSERT INTO retainflow.silver.dim_date
SELECT
  CAST(date_format(calendar_date, 'yyyyMMdd') AS INT) AS date_key,
  calendar_date,
  year(calendar_date) AS calendar_year,
  quarter(calendar_date) AS calendar_quarter,
  month(calendar_date) AS calendar_month,
  date_format(calendar_date, 'MMMM') AS month_name,
  day(calendar_date) AS day_of_month,
  dayofweek(calendar_date) AS day_of_week,
  weekofyear(calendar_date) AS week_of_year,
  dayofweek(calendar_date) IN (1, 7) AS is_weekend,
  calendar_date = last_day(calendar_date) AS is_month_end,
  calendar_date = last_day(add_months(date_trunc('QUARTER', calendar_date), 2)) AS is_quarter_end,
  calendar_date = to_date(concat(year(calendar_date), '-12-31')) AS is_year_end
FROM (
  SELECT explode(sequence(to_date('2021-01-01'), to_date('2026-12-31'), interval 1 day)) AS calendar_date
);

INSERT INTO retainflow.silver.dim_channel
SELECT *
FROM VALUES
  ('CH_WEB', 'WEB', 'Website', 'DIGITAL', true, true, true, current_timestamp(), current_timestamp()),
  ('CH_MOBILE', 'MOBILE', 'Mobile app', 'DIGITAL', true, true, true, current_timestamp(), current_timestamp()),
  ('CH_BRANCH', 'BRANCH', 'Agency branch', 'HUMAN', false, true, true, current_timestamp(), current_timestamp()),
  ('CH_CALL_CENTER', 'CALL_CENTER', 'Call center', 'HUMAN', false, true, true, current_timestamp(), current_timestamp()),
  ('CH_BROKER', 'BROKER', 'Insurance broker', 'PARTNER', false, true, true, current_timestamp(), current_timestamp()),
  ('CH_PARTNER', 'PARTNER', 'Commercial partner', 'PARTNER', false, true, true, current_timestamp(), current_timestamp()),
  ('CH_EMAIL', 'EMAIL', 'Email', 'OUTBOUND', true, false, true, current_timestamp(), current_timestamp()),
  ('CH_SMS', 'SMS', 'SMS', 'OUTBOUND', true, false, true, current_timestamp(), current_timestamp()),
  ('CH_RETENTION_OUTBOUND', 'RETENTION_OUTBOUND', 'Retention outbound team', 'OUTBOUND', false, false, true, current_timestamp(), current_timestamp())
AS channel(
  channel_id,
  channel_code,
  channel_name,
  channel_family,
  is_digital,
  is_inbound,
  is_active,
  created_at,
  updated_at
);

INSERT INTO retainflow.silver.dim_product
SELECT *
FROM VALUES
  ('PROD_AUTO_BASIC', 'AUTO', 'Auto Essential', 'BASIC', 520.00, 600.00, 'MEDIUM', 'MONTHLY', true, current_timestamp(), current_timestamp()),
  ('PROD_AUTO_STANDARD', 'AUTO', 'Auto Comfort', 'STANDARD', 760.00, 350.00, 'MEDIUM', 'MONTHLY', true, current_timestamp(), current_timestamp()),
  ('PROD_AUTO_PREMIUM', 'AUTO', 'Auto Premium', 'PREMIUM', 1120.00, 150.00, 'HIGH', 'MONTHLY', true, current_timestamp(), current_timestamp()),
  ('PROD_HOME_BASIC', 'HOME', 'Home Essential', 'BASIC', 310.00, 500.00, 'LOW', 'MONTHLY', true, current_timestamp(), current_timestamp()),
  ('PROD_HOME_STANDARD', 'HOME', 'Home Comfort', 'STANDARD', 480.00, 300.00, 'MEDIUM', 'MONTHLY', true, current_timestamp(), current_timestamp()),
  ('PROD_HOME_PREMIUM', 'HOME', 'Home Premium', 'PREMIUM', 760.00, 100.00, 'MEDIUM', 'MONTHLY', true, current_timestamp(), current_timestamp()),
  ('PROD_HEALTH_BASIC', 'HEALTH', 'Health Essential', 'BASIC', 680.00, 250.00, 'MEDIUM', 'MONTHLY', true, current_timestamp(), current_timestamp()),
  ('PROD_HEALTH_STANDARD', 'HEALTH', 'Health Comfort', 'STANDARD', 980.00, 100.00, 'HIGH', 'MONTHLY', true, current_timestamp(), current_timestamp()),
  ('PROD_HEALTH_PREMIUM', 'HEALTH', 'Health Premium', 'PREMIUM', 1480.00, 0.00, 'HIGH', 'MONTHLY', true, current_timestamp(), current_timestamp()),
  ('PROD_LIFE_BASIC', 'LIFE', 'Life Essential', 'BASIC', 240.00, 0.00, 'LOW', 'ANNUAL', true, current_timestamp(), current_timestamp()),
  ('PROD_LIFE_STANDARD', 'LIFE', 'Life Comfort', 'STANDARD', 420.00, 0.00, 'MEDIUM', 'ANNUAL', true, current_timestamp(), current_timestamp()),
  ('PROD_LIFE_PREMIUM', 'LIFE', 'Life Premium', 'PREMIUM', 850.00, 0.00, 'HIGH', 'ANNUAL', true, current_timestamp(), current_timestamp()),
  ('PROD_TRAVEL_BASIC', 'TRAVEL', 'Travel Essential', 'BASIC', 80.00, 150.00, 'LOW', 'ANNUAL', true, current_timestamp(), current_timestamp()),
  ('PROD_TRAVEL_STANDARD', 'TRAVEL', 'Travel Comfort', 'STANDARD', 145.00, 75.00, 'LOW', 'ANNUAL', true, current_timestamp(), current_timestamp()),
  ('PROD_TRAVEL_PREMIUM', 'TRAVEL', 'Travel Premium', 'PREMIUM', 260.00, 0.00, 'MEDIUM', 'ANNUAL', true, current_timestamp(), current_timestamp()),
  ('PROD_PET_BASIC', 'PET', 'Pet Essential', 'BASIC', 190.00, 120.00, 'MEDIUM', 'MONTHLY', true, current_timestamp(), current_timestamp()),
  ('PROD_PET_STANDARD', 'PET', 'Pet Comfort', 'STANDARD', 340.00, 60.00, 'MEDIUM', 'MONTHLY', true, current_timestamp(), current_timestamp()),
  ('PROD_PET_PREMIUM', 'PET', 'Pet Premium', 'PREMIUM', 560.00, 0.00, 'HIGH', 'MONTHLY', true, current_timestamp(), current_timestamp()),
  ('PROD_ACCIDENT_BASIC', 'PERSONAL_ACCIDENT', 'Accident Essential', 'BASIC', 130.00, 100.00, 'LOW', 'ANNUAL', true, current_timestamp(), current_timestamp()),
  ('PROD_ACCIDENT_STANDARD', 'PERSONAL_ACCIDENT', 'Accident Comfort', 'STANDARD', 230.00, 50.00, 'MEDIUM', 'ANNUAL', true, current_timestamp(), current_timestamp()),
  ('PROD_ACCIDENT_PREMIUM', 'PERSONAL_ACCIDENT', 'Accident Premium', 'PREMIUM', 390.00, 0.00, 'MEDIUM', 'ANNUAL', true, current_timestamp(), current_timestamp())
AS product(
  product_id,
  product_family,
  product_name,
  coverage_tier,
  base_annual_premium,
  deductible_amount,
  risk_level,
  default_payment_frequency,
  is_active,
  created_at,
  updated_at
);

INSERT INTO retainflow.silver.dim_geography
SELECT *
FROM VALUES
  ('GEO_IDF_PARIS_75015', 'FR', 'Ile-de-France', 'Paris', 'Paris', '75015', 'URBAN', 1.38, 1.05, 1.32, current_timestamp(), current_timestamp()),
  ('GEO_IDF_BOULOGNE_92100', 'FR', 'Ile-de-France', 'Hauts-de-Seine', 'Boulogne-Billancourt', '92100', 'URBAN', 1.42, 0.98, 1.30, current_timestamp(), current_timestamp()),
  ('GEO_IDF_SAINT_DENIS_93200', 'FR', 'Ile-de-France', 'Seine-Saint-Denis', 'Saint-Denis', '93200', 'URBAN', 0.88, 1.18, 1.14, current_timestamp(), current_timestamp()),
  ('GEO_ARA_LYON_69003', 'FR', 'Auvergne-Rhone-Alpes', 'Rhone', 'Lyon', '69003', 'URBAN', 1.16, 1.00, 1.22, current_timestamp(), current_timestamp()),
  ('GEO_ARA_GRENOBLE_38000', 'FR', 'Auvergne-Rhone-Alpes', 'Isere', 'Grenoble', '38000', 'URBAN', 1.07, 1.08, 1.18, current_timestamp(), current_timestamp()),
  ('GEO_PACA_MARSEILLE_13008', 'FR', 'Provence-Alpes-Cote dAzur', 'Bouches-du-Rhone', 'Marseille', '13008', 'URBAN', 1.03, 1.20, 1.12, current_timestamp(), current_timestamp()),
  ('GEO_PACA_NICE_06000', 'FR', 'Provence-Alpes-Cote dAzur', 'Alpes-Maritimes', 'Nice', '06000', 'URBAN', 1.12, 1.14, 1.16, current_timestamp(), current_timestamp()),
  ('GEO_OCC_TOULOUSE_31000', 'FR', 'Occitanie', 'Haute-Garonne', 'Toulouse', '31000', 'URBAN', 1.08, 0.96, 1.20, current_timestamp(), current_timestamp()),
  ('GEO_OCC_MONTPELLIER_34000', 'FR', 'Occitanie', 'Herault', 'Montpellier', '34000', 'URBAN', 1.02, 1.03, 1.18, current_timestamp(), current_timestamp()),
  ('GEO_NAQ_BORDEAUX_33000', 'FR', 'Nouvelle-Aquitaine', 'Gironde', 'Bordeaux', '33000', 'URBAN', 1.10, 0.94, 1.17, current_timestamp(), current_timestamp()),
  ('GEO_NAQ_LIMOGES_87000', 'FR', 'Nouvelle-Aquitaine', 'Haute-Vienne', 'Limoges', '87000', 'SUBURBAN', 0.88, 0.91, 0.96, current_timestamp(), current_timestamp()),
  ('GEO_HDF_LILLE_59000', 'FR', 'Hauts-de-France', 'Nord', 'Lille', '59000', 'URBAN', 0.97, 1.08, 1.15, current_timestamp(), current_timestamp()),
  ('GEO_HDF_AMIENS_80000', 'FR', 'Hauts-de-France', 'Somme', 'Amiens', '80000', 'SUBURBAN', 0.86, 1.02, 0.95, current_timestamp(), current_timestamp()),
  ('GEO_BRE_RENNES_35000', 'FR', 'Bretagne', 'Ille-et-Vilaine', 'Rennes', '35000', 'URBAN', 1.04, 0.88, 1.16, current_timestamp(), current_timestamp()),
  ('GEO_BRE_BREST_29200', 'FR', 'Bretagne', 'Finistere', 'Brest', '29200', 'SUBURBAN', 0.93, 0.95, 1.02, current_timestamp(), current_timestamp()),
  ('GEO_PDL_NANTES_44000', 'FR', 'Pays de la Loire', 'Loire-Atlantique', 'Nantes', '44000', 'URBAN', 1.06, 0.90, 1.17, current_timestamp(), current_timestamp()),
  ('GEO_GE_STRASBOURG_67000', 'FR', 'Grand Est', 'Bas-Rhin', 'Strasbourg', '67000', 'URBAN', 1.03, 0.97, 1.13, current_timestamp(), current_timestamp()),
  ('GEO_GE_REIMS_51100', 'FR', 'Grand Est', 'Marne', 'Reims', '51100', 'SUBURBAN', 0.94, 1.01, 0.99, current_timestamp(), current_timestamp()),
  ('GEO_NOR_ROUEN_76000', 'FR', 'Normandie', 'Seine-Maritime', 'Rouen', '76000', 'URBAN', 0.95, 1.06, 1.02, current_timestamp(), current_timestamp()),
  ('GEO_CVL_TOURS_37000', 'FR', 'Centre-Val de Loire', 'Indre-et-Loire', 'Tours', '37000', 'SUBURBAN', 0.96, 0.92, 1.01, current_timestamp(), current_timestamp()),
  ('GEO_BFC_DIJON_21000', 'FR', 'Bourgogne-Franche-Comte', 'Cote-dOr', 'Dijon', '21000', 'SUBURBAN', 0.98, 0.91, 1.00, current_timestamp(), current_timestamp()),
  ('GEO_COR_AJACCIO_20000', 'FR', 'Corse', 'Corse-du-Sud', 'Ajaccio', '20000', 'SUBURBAN', 0.92, 1.22, 0.91, current_timestamp(), current_timestamp()),
  ('GEO_RURAL_CREUSE_23000', 'FR', 'Nouvelle-Aquitaine', 'Creuse', 'Gueret', '23000', 'RURAL', 0.76, 0.86, 0.72, current_timestamp(), current_timestamp()),
  ('GEO_RURAL_CANTAL_15000', 'FR', 'Auvergne-Rhone-Alpes', 'Cantal', 'Aurillac', '15000', 'RURAL', 0.79, 0.89, 0.74, current_timestamp(), current_timestamp())
AS geography(
  geography_id,
  country,
  region,
  department,
  city,
  postal_code,
  urbanicity,
  income_index,
  claim_risk_index,
  digital_adoption_index,
  created_at,
  updated_at
);

INSERT INTO retainflow.silver.dim_agent
WITH agent_roles AS (
  SELECT *
  FROM VALUES
    ('SALES', 'CH_BRANCH', 'Sales'),
    ('SERVICE', 'CH_CALL_CENTER', 'Service'),
    ('CLAIMS', 'CH_CALL_CENTER', 'Claims'),
    ('RETENTION', 'CH_RETENTION_OUTBOUND', 'Retention'),
    ('HYBRID', 'CH_BROKER', 'Hybrid')
  AS roles(agent_role, channel_id, team_prefix)
),
agent_grid AS (
  SELECT
    g.geography_id,
    g.city,
    r.agent_role,
    r.channel_id,
    r.team_prefix,
    agent_seq
  FROM retainflow.silver.dim_geography g
  CROSS JOIN agent_roles r
  CROSS JOIN (SELECT explode(sequence(1, 2)) AS agent_seq)
)
SELECT
  concat('AGT_', lpad(CAST(row_number() OVER (ORDER BY geography_id, agent_role, agent_seq) AS STRING), 5, '0')) AS agent_id,
  concat('SRC_AGT_', lpad(CAST(row_number() OVER (ORDER BY geography_id, agent_role, agent_seq) AS STRING), 5, '0')) AS source_agent_id,
  concat(team_prefix, ' Advisor ', city, ' ', agent_seq) AS agent_name,
  agent_role,
  channel_id,
  geography_id,
  concat(team_prefix, ' Team ', city) AS team_name,
  date_add(to_date('2016-01-01'), CAST(rand(42) * 3000 AS INT)) AS hire_date,
  true AS is_active,
  current_timestamp() AS created_at,
  current_timestamp() AS updated_at
FROM agent_grid;
