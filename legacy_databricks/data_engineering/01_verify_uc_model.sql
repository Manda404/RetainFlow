-- RetainFlow - Phase 1 Unity Catalog model verification

SHOW SCHEMAS IN retainflow;

SHOW TABLES IN retainflow.silver;
SHOW TABLES IN retainflow.gold;
SHOW TABLES IN retainflow.monitoring;

SELECT *
FROM retainflow.monitoring.generation_config
WHERE is_active = true;

SELECT
  child_schema,
  child_table,
  parent_schema,
  parent_table,
  relationship_type,
  is_required,
  description
FROM retainflow.monitoring.logical_relationships
ORDER BY child_schema, child_table, relationship_id;

SELECT 'silver.dim_date' AS table_name, count(*) AS row_count FROM retainflow.silver.dim_date
UNION ALL SELECT 'silver.dim_geography', count(*) FROM retainflow.silver.dim_geography
UNION ALL SELECT 'silver.dim_channel', count(*) FROM retainflow.silver.dim_channel
UNION ALL SELECT 'silver.dim_agent', count(*) FROM retainflow.silver.dim_agent
UNION ALL SELECT 'silver.dim_product', count(*) FROM retainflow.silver.dim_product
UNION ALL SELECT 'silver.dim_customer', count(*) FROM retainflow.silver.dim_customer
UNION ALL SELECT 'silver.fact_policy', count(*) FROM retainflow.silver.fact_policy
UNION ALL SELECT 'silver.fact_policy_events', count(*) FROM retainflow.silver.fact_policy_events
UNION ALL SELECT 'silver.fact_claims', count(*) FROM retainflow.silver.fact_claims
UNION ALL SELECT 'silver.fact_payments', count(*) FROM retainflow.silver.fact_payments
UNION ALL SELECT 'silver.fact_interactions', count(*) FROM retainflow.silver.fact_interactions
UNION ALL SELECT 'silver.fact_customer_service', count(*) FROM retainflow.silver.fact_customer_service
UNION ALL SELECT 'silver.fact_campaign_contact', count(*) FROM retainflow.silver.fact_campaign_contact
UNION ALL SELECT 'silver.fact_quotes', count(*) FROM retainflow.silver.fact_quotes
UNION ALL SELECT 'silver.fact_retention_actions', count(*) FROM retainflow.silver.fact_retention_actions
UNION ALL SELECT 'gold.customer_360_snapshot', count(*) FROM retainflow.gold.customer_360_snapshot
UNION ALL SELECT 'monitoring.generation_config', count(*) FROM retainflow.monitoring.generation_config
UNION ALL SELECT 'monitoring.generation_batches', count(*) FROM retainflow.monitoring.generation_batches
UNION ALL SELECT 'monitoring.data_quality_results', count(*) FROM retainflow.monitoring.data_quality_results
UNION ALL SELECT 'monitoring.logical_relationships', count(*) FROM retainflow.monitoring.logical_relationships
ORDER BY table_name;
