-- RetainFlow - marketing campaign and quote generation checks

WITH campaign_checks AS (
  SELECT
    count(*) AS campaign_contact_count,
    count(DISTINCT customer_id) AS customers_contacted,
    avg(CASE WHEN opened_flag THEN 1.0 ELSE 0.0 END) AS open_rate,
    avg(CASE WHEN clicked_flag THEN 1.0 ELSE 0.0 END) AS click_rate,
    avg(CASE WHEN responded_flag THEN 1.0 ELSE 0.0 END) AS response_rate,
    avg(CASE WHEN converted_flag THEN 1.0 ELSE 0.0 END) AS conversion_rate
  FROM retainflow.silver.fact_campaign_contact
),
quote_checks AS (
  SELECT
    count(*) AS quote_count,
    count(DISTINCT customer_id) AS customers_with_quote,
    avg(quoted_annual_premium) AS avg_quoted_annual_premium,
    avg(competitor_price_index) AS avg_competitor_price_index,
    min(quote_date) AS min_quote_date,
    max(quote_date) AS max_quote_date,
    count(CASE WHEN quoted_annual_premium <= 0 THEN 1 END) AS non_positive_quote_amount_count,
    count(CASE WHEN competitor_price_index <= 0 THEN 1 END) AS invalid_competitor_price_index_count
  FROM retainflow.silver.fact_quotes
),
customer_count AS (
  SELECT count(*) AS customer_count
  FROM retainflow.silver.dim_customer
),
duplicate_campaign_contacts AS (
  SELECT count(*) AS duplicate_campaign_contact_id_count
  FROM (
    SELECT campaign_contact_id
    FROM retainflow.silver.fact_campaign_contact
    GROUP BY campaign_contact_id
    HAVING count(*) > 1
  )
),
duplicate_quotes AS (
  SELECT count(*) AS duplicate_quote_id_count
  FROM (
    SELECT quote_id
    FROM retainflow.silver.fact_quotes
    GROUP BY quote_id
    HAVING count(*) > 1
  )
),
orphan_campaign_customer AS (
  SELECT count(*) AS orphan_campaign_customer_count
  FROM retainflow.silver.fact_campaign_contact cc
  LEFT JOIN retainflow.silver.dim_customer c
    ON cc.customer_id = c.customer_id
  WHERE c.customer_id IS NULL
),
orphan_campaign_channel AS (
  SELECT count(*) AS orphan_campaign_channel_count
  FROM retainflow.silver.fact_campaign_contact cc
  LEFT JOIN retainflow.silver.dim_channel ch
    ON cc.channel_id = ch.channel_id
  WHERE ch.channel_id IS NULL
),
orphan_quote_customer AS (
  SELECT count(*) AS orphan_quote_customer_count
  FROM retainflow.silver.fact_quotes q
  LEFT JOIN retainflow.silver.dim_customer c
    ON q.customer_id = c.customer_id
  WHERE c.customer_id IS NULL
),
orphan_quote_product AS (
  SELECT count(*) AS orphan_quote_product_count
  FROM retainflow.silver.fact_quotes q
  LEFT JOIN retainflow.silver.dim_product p
    ON q.product_id = p.product_id
  WHERE p.product_id IS NULL
),
orphan_quote_channel AS (
  SELECT count(*) AS orphan_quote_channel_count
  FROM retainflow.silver.fact_quotes q
  LEFT JOIN retainflow.silver.dim_channel ch
    ON q.channel_id = ch.channel_id
  WHERE ch.channel_id IS NULL
),
orphan_quote_agent AS (
  SELECT count(*) AS orphan_quote_agent_count
  FROM retainflow.silver.fact_quotes q
  LEFT JOIN retainflow.silver.dim_agent a
    ON q.agent_id = a.agent_id
  WHERE q.agent_id IS NOT NULL
    AND a.agent_id IS NULL
)
SELECT 'customer_count' AS metric, CAST(customer_count AS STRING) AS value FROM customer_count
UNION ALL SELECT 'campaign_contact_count', CAST(campaign_contact_count AS STRING) FROM campaign_checks
UNION ALL SELECT 'customers_contacted', CAST(customers_contacted AS STRING) FROM campaign_checks
UNION ALL SELECT 'avg_campaign_contacts_per_customer', CAST(round(campaign_contact_count / customer_count, 4) AS STRING) FROM campaign_checks CROSS JOIN customer_count
UNION ALL SELECT 'open_rate', CAST(round(open_rate, 4) AS STRING) FROM campaign_checks
UNION ALL SELECT 'click_rate', CAST(round(click_rate, 4) AS STRING) FROM campaign_checks
UNION ALL SELECT 'response_rate', CAST(round(response_rate, 4) AS STRING) FROM campaign_checks
UNION ALL SELECT 'conversion_rate', CAST(round(conversion_rate, 4) AS STRING) FROM campaign_checks
UNION ALL SELECT 'quote_count', CAST(quote_count AS STRING) FROM quote_checks
UNION ALL SELECT 'customers_with_quote', CAST(customers_with_quote AS STRING) FROM quote_checks
UNION ALL SELECT 'avg_quoted_annual_premium', CAST(round(avg_quoted_annual_premium, 2) AS STRING) FROM quote_checks
UNION ALL SELECT 'avg_competitor_price_index', CAST(round(avg_competitor_price_index, 4) AS STRING) FROM quote_checks
UNION ALL SELECT 'min_quote_date', CAST(min_quote_date AS STRING) FROM quote_checks
UNION ALL SELECT 'max_quote_date', CAST(max_quote_date AS STRING) FROM quote_checks
UNION ALL SELECT 'non_positive_quote_amount_count', CAST(non_positive_quote_amount_count AS STRING) FROM quote_checks
UNION ALL SELECT 'invalid_competitor_price_index_count', CAST(invalid_competitor_price_index_count AS STRING) FROM quote_checks
UNION ALL SELECT 'duplicate_campaign_contact_id_count', CAST(duplicate_campaign_contact_id_count AS STRING) FROM duplicate_campaign_contacts
UNION ALL SELECT 'duplicate_quote_id_count', CAST(duplicate_quote_id_count AS STRING) FROM duplicate_quotes
UNION ALL SELECT 'orphan_campaign_customer_count', CAST(orphan_campaign_customer_count AS STRING) FROM orphan_campaign_customer
UNION ALL SELECT 'orphan_campaign_channel_count', CAST(orphan_campaign_channel_count AS STRING) FROM orphan_campaign_channel
UNION ALL SELECT 'orphan_quote_customer_count', CAST(orphan_quote_customer_count AS STRING) FROM orphan_quote_customer
UNION ALL SELECT 'orphan_quote_product_count', CAST(orphan_quote_product_count AS STRING) FROM orphan_quote_product
UNION ALL SELECT 'orphan_quote_channel_count', CAST(orphan_quote_channel_count AS STRING) FROM orphan_quote_channel
UNION ALL SELECT 'orphan_quote_agent_count', CAST(orphan_quote_agent_count AS STRING) FROM orphan_quote_agent
ORDER BY metric;

SELECT campaign_type, channel_id, count(*) AS contacts, round(avg(CASE WHEN converted_flag THEN 1.0 ELSE 0.0 END), 4) AS conversion_rate
FROM retainflow.silver.fact_campaign_contact
GROUP BY campaign_type, channel_id
ORDER BY contacts DESC;

SELECT quote_status, count(*) AS quotes, round(avg(quoted_annual_premium), 2) AS avg_quoted_annual_premium
FROM retainflow.silver.fact_quotes
GROUP BY quote_status
ORDER BY quotes DESC;

SELECT pr.product_family, count(*) AS quotes, round(avg(q.quoted_annual_premium), 2) AS avg_quoted_annual_premium
FROM retainflow.silver.fact_quotes q
JOIN retainflow.silver.dim_product pr
  ON q.product_id = pr.product_id
GROUP BY pr.product_family
ORDER BY quotes DESC;
