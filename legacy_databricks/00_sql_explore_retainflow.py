# Databricks notebook source
# MAGIC %md
# MAGIC # RetainFlow - SQL Exploration
# MAGIC
# MAGIC Notebook d'exploration pour tester des commandes SQL et visualiser le contenu des tables creees dans Unity Catalog.
# MAGIC
# MAGIC Prerequis :
# MAGIC - Le pipeline `data_engineering/run_phase1_pipeline.py` a deja ete execute.
# MAGIC - Le catalog `retainflow` existe.
# MAGIC - Les tables `silver`, `gold` et `monitoring` sont disponibles.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Contexte SQL

# COMMAND ----------

# MAGIC %sql
# MAGIC USE CATALOG retainflow;

# COMMAND ----------

# MAGIC %sql
# MAGIC SHOW SCHEMAS IN retainflow;

# COMMAND ----------

# MAGIC %sql
# MAGIC SHOW TABLES IN retainflow.silver;

# COMMAND ----------

# MAGIC %sql
# MAGIC SHOW TABLES IN retainflow.gold;

# COMMAND ----------

# MAGIC %sql
# MAGIC SHOW TABLES IN retainflow.monitoring;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Configuration Et Volumes

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT *
# MAGIC FROM retainflow.monitoring.generation_config
# MAGIC WHERE is_active = true;

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT 'silver.dim_date' AS table_name, count(*) AS row_count FROM retainflow.silver.dim_date
# MAGIC UNION ALL SELECT 'silver.dim_geography', count(*) FROM retainflow.silver.dim_geography
# MAGIC UNION ALL SELECT 'silver.dim_channel', count(*) FROM retainflow.silver.dim_channel
# MAGIC UNION ALL SELECT 'silver.dim_agent', count(*) FROM retainflow.silver.dim_agent
# MAGIC UNION ALL SELECT 'silver.dim_product', count(*) FROM retainflow.silver.dim_product
# MAGIC UNION ALL SELECT 'silver.dim_customer', count(*) FROM retainflow.silver.dim_customer
# MAGIC UNION ALL SELECT 'silver.fact_policy', count(*) FROM retainflow.silver.fact_policy
# MAGIC UNION ALL SELECT 'silver.fact_policy_events', count(*) FROM retainflow.silver.fact_policy_events
# MAGIC UNION ALL SELECT 'silver.fact_payments', count(*) FROM retainflow.silver.fact_payments
# MAGIC UNION ALL SELECT 'silver.fact_claims', count(*) FROM retainflow.silver.fact_claims
# MAGIC UNION ALL SELECT 'silver.fact_interactions', count(*) FROM retainflow.silver.fact_interactions
# MAGIC UNION ALL SELECT 'silver.fact_customer_service', count(*) FROM retainflow.silver.fact_customer_service
# MAGIC UNION ALL SELECT 'silver.fact_campaign_contact', count(*) FROM retainflow.silver.fact_campaign_contact
# MAGIC UNION ALL SELECT 'silver.fact_quotes', count(*) FROM retainflow.silver.fact_quotes
# MAGIC UNION ALL SELECT 'silver.fact_retention_actions', count(*) FROM retainflow.silver.fact_retention_actions
# MAGIC UNION ALL SELECT 'gold.customer_360_snapshot', count(*) FROM retainflow.gold.customer_360_snapshot
# MAGIC UNION ALL SELECT 'monitoring.logical_relationships', count(*) FROM retainflow.monitoring.logical_relationships
# MAGIC UNION ALL SELECT 'monitoring.generation_batches', count(*) FROM retainflow.monitoring.generation_batches
# MAGIC UNION ALL SELECT 'monitoring.data_quality_results', count(*) FROM retainflow.monitoring.data_quality_results
# MAGIC ORDER BY table_name;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Apercu Des Tables De Reference

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT *
# MAGIC FROM retainflow.silver.dim_product
# MAGIC ORDER BY product_family, coverage_tier;

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT *
# MAGIC FROM retainflow.silver.dim_channel
# MAGIC ORDER BY channel_family, channel_code;

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT *
# MAGIC FROM retainflow.silver.dim_geography
# MAGIC ORDER BY region, city;

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT *
# MAGIC FROM retainflow.silver.dim_agent
# MAGIC ORDER BY geography_id, agent_role, agent_id
# MAGIC LIMIT 50;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Exploration Clients

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT *
# MAGIC FROM retainflow.silver.dim_customer
# MAGIC LIMIT 100;

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT
# MAGIC   customer_segment,
# MAGIC   count(*) AS customers,
# MAGIC   round(avg(price_sensitivity_score), 3) AS avg_price_sensitivity,
# MAGIC   round(avg(digital_engagement_score), 3) AS avg_digital_engagement,
# MAGIC   round(avg(loyalty_score), 3) AS avg_loyalty
# MAGIC FROM retainflow.silver.dim_customer
# MAGIC GROUP BY customer_segment
# MAGIC ORDER BY customers DESC;

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT
# MAGIC   estimated_income_band,
# MAGIC   digital_profile,
# MAGIC   count(*) AS customers
# MAGIC FROM retainflow.silver.dim_customer
# MAGIC GROUP BY estimated_income_band, digital_profile
# MAGIC ORDER BY estimated_income_band, digital_profile;

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT
# MAGIC   g.region,
# MAGIC   g.urbanicity,
# MAGIC   count(*) AS customers,
# MAGIC   round(avg(c.price_sensitivity_score), 3) AS avg_price_sensitivity,
# MAGIC   round(avg(c.claim_propensity_score), 3) AS avg_claim_propensity
# MAGIC FROM retainflow.silver.dim_customer c
# MAGIC JOIN retainflow.silver.dim_geography g
# MAGIC   ON c.geography_id = g.geography_id
# MAGIC GROUP BY g.region, g.urbanicity
# MAGIC ORDER BY customers DESC;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Exploration Contrats

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT *
# MAGIC FROM retainflow.silver.fact_policy
# MAGIC LIMIT 100;

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT
# MAGIC   policy_status,
# MAGIC   count(*) AS policies,
# MAGIC   round(avg(annual_premium), 2) AS avg_annual_premium,
# MAGIC   round(avg(premium_increase_pct_last_renewal), 4) AS avg_premium_increase_pct
# MAGIC FROM retainflow.silver.fact_policy
# MAGIC GROUP BY policy_status
# MAGIC ORDER BY policies DESC;

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT
# MAGIC   pr.product_family,
# MAGIC   pr.coverage_tier,
# MAGIC   count(*) AS policies,
# MAGIC   round(avg(p.annual_premium), 2) AS avg_annual_premium
# MAGIC FROM retainflow.silver.fact_policy p
# MAGIC JOIN retainflow.silver.dim_product pr
# MAGIC   ON p.product_id = pr.product_id
# MAGIC GROUP BY pr.product_family, pr.coverage_tier
# MAGIC ORDER BY pr.product_family, pr.coverage_tier;

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT
# MAGIC   c.customer_segment,
# MAGIC   count(*) AS policies,
# MAGIC   count(DISTINCT p.customer_id) AS customers,
# MAGIC   round(count(*) / count(DISTINCT p.customer_id), 2) AS avg_policies_per_customer,
# MAGIC   round(avg(p.annual_premium), 2) AS avg_annual_premium
# MAGIC FROM retainflow.silver.fact_policy p
# MAGIC JOIN retainflow.silver.dim_customer c
# MAGIC   ON p.customer_id = c.customer_id
# MAGIC GROUP BY c.customer_segment
# MAGIC ORDER BY policies DESC;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Exploration Evenements De Contrats

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT *
# MAGIC FROM retainflow.silver.fact_policy_events
# MAGIC ORDER BY event_timestamp DESC
# MAGIC LIMIT 100;

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT
# MAGIC   event_type,
# MAGIC   count(*) AS events,
# MAGIC   min(event_date) AS first_event_date,
# MAGIC   max(event_date) AS last_event_date
# MAGIC FROM retainflow.silver.fact_policy_events
# MAGIC GROUP BY event_type
# MAGIC ORDER BY events DESC;

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT
# MAGIC   event_type,
# MAGIC   year(event_date) AS event_year,
# MAGIC   count(*) AS events
# MAGIC FROM retainflow.silver.fact_policy_events
# MAGIC GROUP BY event_type, year(event_date)
# MAGIC ORDER BY event_year, event_type;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Exploration Paiements

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT *
# MAGIC FROM retainflow.silver.fact_payments
# MAGIC LIMIT 100;

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT
# MAGIC   payment_status,
# MAGIC   count(*) AS payments,
# MAGIC   round(avg(payment_amount), 2) AS avg_payment_amount,
# MAGIC   round(avg(coalesce(days_late, 0)), 2) AS avg_days_late
# MAGIC FROM retainflow.silver.fact_payments
# MAGIC GROUP BY payment_status
# MAGIC ORDER BY payments DESC;

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT
# MAGIC   payment_year,
# MAGIC   payment_status,
# MAGIC   count(*) AS payments,
# MAGIC   round(sum(payment_amount), 2) AS total_payment_amount
# MAGIC FROM retainflow.silver.fact_payments
# MAGIC GROUP BY payment_year, payment_status
# MAGIC ORDER BY payment_year, payment_status;

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT
# MAGIC   c.customer_segment,
# MAGIC   count(*) AS payments,
# MAGIC   sum(CASE WHEN pay.payment_status IN ('LATE', 'REJECTED', 'WRITTEN_OFF') THEN 1 ELSE 0 END) AS payment_incidents,
# MAGIC   round(sum(CASE WHEN pay.payment_status IN ('LATE', 'REJECTED', 'WRITTEN_OFF') THEN 1 ELSE 0 END) / count(*), 4) AS incident_rate
# MAGIC FROM retainflow.silver.fact_payments pay
# MAGIC JOIN retainflow.silver.dim_customer c
# MAGIC   ON pay.customer_id = c.customer_id
# MAGIC GROUP BY c.customer_segment
# MAGIC ORDER BY incident_rate DESC;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. Parcours Client 360 Simplifie

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT
# MAGIC   c.customer_id,
# MAGIC   c.first_name,
# MAGIC   c.last_name,
# MAGIC   c.customer_segment,
# MAGIC   c.estimated_income_band,
# MAGIC   c.digital_profile,
# MAGIC   count(DISTINCT p.policy_id) AS policy_count,
# MAGIC   round(sum(p.annual_premium), 2) AS total_annual_premium,
# MAGIC   count(DISTINCT CASE WHEN pay.payment_status IN ('LATE', 'REJECTED', 'WRITTEN_OFF') THEN pay.payment_id END) AS payment_incidents,
# MAGIC   max(p.premium_increase_pct_last_renewal) AS max_premium_increase_pct,
# MAGIC   min(p.next_renewal_date) AS next_renewal_date
# MAGIC FROM retainflow.silver.dim_customer c
# MAGIC LEFT JOIN retainflow.silver.fact_policy p
# MAGIC   ON c.customer_id = p.customer_id
# MAGIC LEFT JOIN retainflow.silver.fact_payments pay
# MAGIC   ON p.policy_id = pay.policy_id
# MAGIC GROUP BY
# MAGIC   c.customer_id,
# MAGIC   c.first_name,
# MAGIC   c.last_name,
# MAGIC   c.customer_segment,
# MAGIC   c.estimated_income_band,
# MAGIC   c.digital_profile
# MAGIC ORDER BY payment_incidents DESC, total_annual_premium DESC
# MAGIC LIMIT 100;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 9. Relations Logiques Et Audit

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT *
# MAGIC FROM retainflow.monitoring.logical_relationships
# MAGIC ORDER BY child_schema, child_table, relationship_id;

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT *
# MAGIC FROM retainflow.monitoring.generation_batches
# MAGIC ORDER BY run_finished_at DESC
# MAGIC LIMIT 20;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 10. Zone Libre
# MAGIC
# MAGIC Utilise les cellules ci-dessous pour tester tes propres commandes SQL.

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT current_catalog() AS current_catalog, current_schema() AS current_schema, current_user() AS current_user;

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Exemple : remplace cette requete par tes propres tests.
# MAGIC SELECT *
# MAGIC FROM retainflow.silver.dim_customer
# MAGIC WHERE customer_segment = 'PRICE_SENSITIVE'
# MAGIC LIMIT 20;
