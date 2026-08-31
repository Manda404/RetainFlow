-- RetainFlow - data quality result summary

SELECT
  check_status,
  count(*) AS checks
FROM retainflow.monitoring.data_quality_results
GROUP BY check_status
ORDER BY check_status;

SELECT
  schema_name,
  table_name,
  check_status,
  count(*) AS checks,
  sum(failed_row_count) AS failed_rows
FROM retainflow.monitoring.data_quality_results
GROUP BY schema_name, table_name, check_status
ORDER BY schema_name, table_name, check_status;

SELECT
  schema_name,
  table_name,
  check_name,
  check_type,
  check_status,
  observed_value,
  expected_value,
  failed_row_count,
  check_message,
  checked_at
FROM retainflow.monitoring.data_quality_results
WHERE check_status <> 'PASS'
ORDER BY failed_row_count DESC, schema_name, table_name, check_name;

SELECT *
FROM retainflow.monitoring.data_quality_results
ORDER BY schema_name, table_name, check_name;
