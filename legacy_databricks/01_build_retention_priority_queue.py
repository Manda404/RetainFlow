# Databricks notebook source
# MAGIC %md
# MAGIC # RetainFlow - Build Retention Priority Queue
# MAGIC
# MAGIC Convert churn model scores into prioritized business recommendations.

# COMMAND ----------

from pyspark.sql import functions as F

# COMMAND ----------

dbutils.widgets.text("catalog", "retainflow")
dbutils.widgets.text("prediction_schema", "ml")
dbutils.widgets.text("prediction_table", "churn_predictions")
dbutils.widgets.text("gold_schema", "gold")
dbutils.widgets.text("customer_360_table", "customer_360_snapshot")
dbutils.widgets.text("output_table", "retention_priority_queue")
dbutils.widgets.text("min_churn_probability", "0.18")

catalog = dbutils.widgets.get("catalog")
prediction_schema = dbutils.widgets.get("prediction_schema")
prediction_table = dbutils.widgets.get("prediction_table")
gold_schema = dbutils.widgets.get("gold_schema")
customer_360_table = dbutils.widgets.get("customer_360_table")
output_table = dbutils.widgets.get("output_table")
min_churn_probability = float(dbutils.widgets.get("min_churn_probability"))

prediction_fqn = f"{catalog}.{prediction_schema}.{prediction_table}"
customer_360_fqn = f"{catalog}.{gold_schema}.{customer_360_table}"
output_fqn = f"{catalog}.{gold_schema}.{output_table}"
channel_fqn = f"{catalog}.silver.dim_channel"

# COMMAND ----------

predictions = spark.table(prediction_fqn)
customer_360 = spark.table(customer_360_fqn)
channels = spark.table(channel_fqn)

prediction_count = predictions.count()
if prediction_count == 0:
    raise ValueError(
        f"{prediction_fqn} is empty. Run churn_model/01_train_churn_model.py before this notebook."
    )

# COMMAND ----------

base = (
    predictions.alias("p")
    .join(customer_360.alias("g"), on=["observation_date", "customer_id"], how="inner")
    .where(F.col("p.churn_probability") >= F.lit(min_churn_probability))
)

recommendations = (
    base
    .withColumn(
        "recommended_action_type",
        F.when(F.col("premium_increase_pct_max_12m") >= 0.12, F.lit("DISCOUNT"))
        .when(F.col("payment_incidents_6m") >= 2, F.lit("PAYMENT_PLAN"))
        .when(F.col("complaints_6m") >= 1, F.lit("CALLBACK"))
        .when(F.col("total_claims_12m") >= 2, F.lit("CLAIM_REVIEW"))
        .when(F.col("number_of_products") <= 1, F.lit("COVERAGE_UPGRADE"))
        .otherwise(F.lit("LOYALTY_BONUS")),
    )
    .withColumn(
        "action_reason",
        F.when(F.col("premium_increase_pct_max_12m") >= 0.12, F.lit("Premium increase sensitivity"))
        .when(F.col("payment_incidents_6m") >= 2, F.lit("Recent payment incidents"))
        .when(F.col("complaints_6m") >= 1, F.lit("Recent service complaint"))
        .when(F.col("total_claims_12m") >= 2, F.lit("Claims experience risk"))
        .when(F.col("number_of_products") <= 1, F.lit("Low product depth"))
        .otherwise(F.lit("High churn risk")),
    )
    .withColumn(
        "recommended_channel_code",
        F.when(F.col("recommended_action_type").isin("CALLBACK", "CLAIM_REVIEW"), F.lit("CALL_CENTER"))
        .when(F.col("recommended_action_type") == "PAYMENT_PLAN", F.lit("EMAIL"))
        .when(F.col("churn_risk_band").isin("VERY_HIGH", "HIGH"), F.lit("RETENTION_OUTBOUND"))
        .otherwise(F.lit("EMAIL")),
    )
    .withColumn(
        "estimated_offer_value",
        F.when(
            F.col("recommended_action_type") == "DISCOUNT",
            F.round(F.col("total_annual_premium").cast("double") * F.lit(0.08), 2),
        )
        .when(F.col("recommended_action_type") == "LOYALTY_BONUS", F.lit(50.00))
        .when(F.col("recommended_action_type") == "COVERAGE_UPGRADE", F.lit(75.00))
        .otherwise(F.lit(0.00))
        .cast("decimal(12,2)"),
    )
    .withColumn(
        "priority_score",
        F.round(
            F.col("churn_probability") * F.lit(70.0)
            + F.col("customer_value_score") * F.lit(25.0)
            + F.when(F.col("renewal_days_min").between(0, 45), F.lit(5.0)).otherwise(F.lit(0.0)),
            4,
        ),
    )
    .withColumn(
        "priority_tier",
        F.when(F.col("priority_score") >= 70, F.lit("P1"))
        .when(F.col("priority_score") >= 55, F.lit("P2"))
        .when(F.col("priority_score") >= 40, F.lit("P3"))
        .otherwise(F.lit("P4")),
    )
)

# COMMAND ----------

final_queue = (
    recommendations.alias("r")
    .join(
        channels.select("channel_id", "channel_code", "channel_name").alias("ch"),
        F.col("r.recommended_channel_code") == F.col("ch.channel_code"),
        "left",
    )
    .select(
        F.concat(
            F.lit("REC_"),
            F.substring(
                F.sha2(
                    F.concat_ws(
                        "|",
                        F.col("r.observation_date").cast("string"),
                        F.col("r.customer_id"),
                        F.col("r.scoring_run_id"),
                    ),
                    256,
                ),
                1,
                24,
            ),
        ).alias("recommendation_id"),
        F.col("r.observation_date"),
        F.col("r.customer_id"),
        F.col("r.churn_probability").cast("double").alias("churn_probability"),
        F.col("r.churn_risk_band"),
        F.col("r.priority_score"),
        F.col("r.priority_tier"),
        F.col("r.recommended_action_type"),
        F.col("r.action_reason"),
        F.col("ch.channel_id").alias("recommended_channel_id"),
        F.col("ch.channel_name").alias("recommended_channel_name"),
        F.col("r.estimated_offer_value"),
        F.col("r.customer_value_score"),
        F.col("r.total_annual_premium"),
        F.col("r.renewal_days_min"),
        F.col("r.model_name"),
        F.col("r.scoring_run_id"),
        F.current_timestamp().alias("created_at"),
    )
    .orderBy(F.desc("priority_score"), F.desc("churn_probability"))
)

(
    final_queue.write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(output_fqn)
)

# COMMAND ----------

display(
    final_queue.groupBy("priority_tier", "recommended_action_type")
    .agg(
        F.count("*").alias("customers"),
        F.round(F.avg("churn_probability"), 4).alias("avg_churn_probability"),
        F.round(F.avg("priority_score"), 2).alias("avg_priority_score"),
        F.round(F.sum("estimated_offer_value"), 2).alias("total_offer_budget"),
    )
    .orderBy("priority_tier", F.desc("customers"))
)

# COMMAND ----------

display(
    final_queue
    .select(
        "priority_tier",
        "customer_id",
        "churn_probability",
        "priority_score",
        "recommended_action_type",
        "action_reason",
        "recommended_channel_name",
        "estimated_offer_value",
        "renewal_days_min",
    )
    .orderBy(F.desc("priority_score"))
    .limit(100)
)
