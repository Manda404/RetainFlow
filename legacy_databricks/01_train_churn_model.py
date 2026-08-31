# Databricks notebook source
# MAGIC %md
# MAGIC # RetainFlow - Churn Modeling With CatBoost
# MAGIC
# MAGIC Objectif du notebook :
# MAGIC
# MAGIC 1. charger la configuration YAML du projet
# MAGIC 2. lire les tables Delta `features` et `labels`
# MAGIC 3. construire le dataset supervisé churn
# MAGIC 4. vérifier les volumes et la distribution de la cible
# MAGIC 5. convertir le DataFrame Spark en dataset Pandas avec `toPandas()`
# MAGIC 6. préparer les variables numériques et catégorielles
# MAGIC 7. créer les splits train / validation / test
# MAGIC 8. entraîner un modèle CatBoostClassifier
# MAGIC 9. évaluer le modèle avec AUC, average precision, accuracy et F1
# MAGIC 10. produire les matrices de confusion validation/test
# MAGIC 11. logger paramètres, métriques, artifacts et modèle dans MLflow
# MAGIC 12. scorer tous les clients
# MAGIC 13. écrire les prédictions dans `retainflow.ml.churn_predictions`

# COMMAND ----------

# MAGIC %md
# MAGIC ## 0. Installation Des Librairies
# MAGIC
# MAGIC CatBoost et scikit-learn sont utilisés pour le modèle. Spark reste utilisé pour lire et écrire les tables Databricks.

# COMMAND ----------

# MAGIC %pip install catboost scikit-learn pyyaml

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Imports Et Chargement Du Code Projet
# MAGIC
# MAGIC Le notebook reste une orchestration. Les fonctions réutilisables vivent dans le package `retainflow`.

# COMMAND ----------

from pathlib import Path
import json
import sys

import mlflow
import mlflow.catboost
import pandas as pd
from catboost import CatBoostClassifier
from pyspark.sql import functions as F

PROJECT_ROOT = Path("/Workspace/Users/s239150.eps@gmail.com/RetainFlow")
LOCAL_PROJECT_ROOT = Path.cwd()

for path in (PROJECT_ROOT, LOCAL_PROJECT_ROOT):
    if str(path) not in sys.path:
        sys.path.append(str(path))

from retainflow.churn import (
    CATEGORICAL_FEATURES,
    FEATURE_COLUMNS,
    NUMERIC_FEATURES,
    build_confusion_matrix,
    build_feature_importance,
    build_feature_profile,
    build_label_distribution,
    build_split_summary,
    build_training_dataset,
    evaluate_classifier,
    log_churn_artifacts,
    make_pool,
    make_scores,
    split_dataset,
    to_modeling_pandas,
)
from retainflow.config import load_churn_model_config

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Lecture De La Configuration YAML
# MAGIC
# MAGIC Toute la configuration vient de `config/churn_model.yml`.
# MAGIC Il n'y a pas de `dbutils.widgets` pour les paramètres du modèle.

# COMMAND ----------

CONFIG_PATH = PROJECT_ROOT / "config" / "churn_model.yml"

if not CONFIG_PATH.exists():
    CONFIG_PATH = LOCAL_PROJECT_ROOT / "config" / "churn_model.yml"

config = load_churn_model_config(CONFIG_PATH)

config

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Tables Utilisées
# MAGIC
# MAGIC On explicite les tables d'entrée et de sortie pour vérifier que le modèle travaille sur les bons objets Unity Catalog.

# COMMAND ----------

tables = {
    "feature_table": config.feature_fqn,
    "label_table": config.label_fqn,
    "prediction_table": config.prediction_fqn,
    "experiment_name": config.experiment_name,
    "registered_model_name": config.registered_model_name,
}

tables

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Lecture Spark Des Features Et Labels
# MAGIC
# MAGIC Spark lit les tables Delta. À cette étape, on reste distribué côté Databricks.

# COMMAND ----------

features_spark = spark.table(config.feature_fqn)
labels_spark = spark.table(config.label_fqn)

display(
    spark.createDataFrame(
        [
            ("features", config.feature_fqn, features_spark.count()),
            ("labels", config.label_fqn, labels_spark.count()),
        ],
        ["asset", "table_name", "rows"],
    )
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Construction Du Dataset Supervisé
# MAGIC
# MAGIC On joint les features et les labels sur :
# MAGIC
# MAGIC - `observation_date`
# MAGIC - `customer_id`
# MAGIC
# MAGIC On ajoute aussi `split_bucket`, un bucket stable dérivé du `customer_id`, pour obtenir des splits reproductibles.

# COMMAND ----------

training_dataset_spark = build_training_dataset(spark, config)

display(training_dataset_spark.limit(20))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Contrôles Avant Modélisation
# MAGIC
# MAGIC Avant d'entraîner, on vérifie la volumétrie, la distribution du label churn et la cohérence du dataset.

# COMMAND ----------

display(
    training_dataset_spark.agg(
        F.count("*").alias("rows"),
        F.countDistinct("customer_id").alias("customers"),
        F.avg("label").alias("churn_rate"),
        F.min("synthetic_churn_probability").alias("min_synthetic_probability"),
        F.max("synthetic_churn_probability").alias("max_synthetic_probability"),
    )
)

# COMMAND ----------

display(
    training_dataset_spark.groupBy("synthetic_churn_risk_band")
    .agg(
        F.count("*").alias("customers"),
        F.round(F.avg("label"), 4).alias("churn_rate"),
        F.round(F.avg("synthetic_churn_probability"), 4).alias("avg_synthetic_probability"),
    )
    .orderBy(F.desc("avg_synthetic_probability"))
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Définition Des Variables Du Modèle
# MAGIC
# MAGIC CatBoost gère nativement les variables catégorielles. On garde donc :
# MAGIC
# MAGIC - les colonnes numériques dans `NUMERIC_FEATURES`
# MAGIC - les colonnes catégorielles dans `CATEGORICAL_FEATURES`
# MAGIC - toutes les features dans `FEATURE_COLUMNS`

# COMMAND ----------

feature_definition = {
    "numeric_features": NUMERIC_FEATURES,
    "categorical_features": CATEGORICAL_FEATURES,
    "feature_columns": FEATURE_COLUMNS,
}

feature_definition

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. Conversion Spark Vers Pandas
# MAGIC
# MAGIC Ici on utilise explicitement `toPandas()`.
# MAGIC
# MAGIC Pour ce projet, c'est acceptable parce qu'on travaille sur un volume contrôlé avec `--n-customers`. Pour de très gros volumes, il faudrait passer sur un entraînement distribué ou échantillonner.

# COMMAND ----------

dataset_pd = to_modeling_pandas(training_dataset_spark)

dataset_pd.head(10)

# COMMAND ----------

dataset_pd.info()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 9. Préparation Des Splits Train / Validation / Test
# MAGIC
# MAGIC Le split est stable :
# MAGIC
# MAGIC - train : `split_bucket < 70`
# MAGIC - validation : `70 <= split_bucket < 85`
# MAGIC - test : `split_bucket >= 85`

# COMMAND ----------

train_pd, valid_pd, test_pd = split_dataset(dataset_pd)

split_summary = build_split_summary(train_pd, valid_pd, test_pd)

display(spark.createDataFrame(split_summary))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 9.1 Distribution De La Cible
# MAGIC
# MAGIC Cette table sera loggée dans MLflow pour garder une trace de la distribution du label au moment de l'entraînement.

# COMMAND ----------

label_distribution_pd = build_label_distribution(dataset_pd)

display(spark.createDataFrame(label_distribution_pd))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 9.2 Profil Des Features
# MAGIC
# MAGIC On calcule un profil simple des variables numériques et catégorielles. Il sera conservé comme artifact MLflow.

# COMMAND ----------

feature_profile_pd = build_feature_profile(dataset_pd)

display(spark.createDataFrame(feature_profile_pd.fillna("").astype(str)))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 10. Création Des Pools CatBoost
# MAGIC
# MAGIC Les `Pool` CatBoost contiennent :
# MAGIC
# MAGIC - `X` : les features
# MAGIC - `y` : le label churn
# MAGIC - `cat_features` : les index des variables catégorielles

# COMMAND ----------

train_pool = make_pool(train_pd)
valid_pool = make_pool(valid_pd)
test_pool = make_pool(test_pd)

cat_feature_indices = [FEATURE_COLUMNS.index(column) for column in CATEGORICAL_FEATURES]

{
    "feature_count": len(FEATURE_COLUMNS),
    "categorical_feature_indices": cat_feature_indices,
}

# COMMAND ----------

# MAGIC %md
# MAGIC ## 11. Initialisation Du Modèle CatBoost
# MAGIC
# MAGIC Les hyperparamètres viennent du YAML :
# MAGIC
# MAGIC - `iterations`
# MAGIC - `learning_rate`
# MAGIC - `depth`
# MAGIC - `prediction_threshold`

# COMMAND ----------

model = CatBoostClassifier(
    iterations=config.iterations,
    learning_rate=config.learning_rate,
    depth=config.depth,
    loss_function="Logloss",
    eval_metric="AUC",
    random_seed=42,
    auto_class_weights="Balanced",
    verbose=50,
)

model.get_params()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 12. Entraînement Avec MLflow
# MAGIC
# MAGIC On logge :
# MAGIC
# MAGIC - la configuration YAML
# MAGIC - les tables Unity Catalog utilisées
# MAGIC - le contrat de features
# MAGIC - le résumé train / validation / test
# MAGIC - la distribution du label
# MAGIC - le profil des features
# MAGIC - les métriques validation/test
# MAGIC - les matrices de confusion
# MAGIC - l'importance des variables
# MAGIC - un échantillon du dataset et des prédictions
# MAGIC - le modèle CatBoost

# COMMAND ----------

mlflow.set_experiment(config.experiment_name)

with mlflow.start_run(run_name="retainflow_churn_catboost") as run:
    mlflow.log_params(
        {
            "catalog": config.catalog,
            "feature_table_fqn": config.feature_fqn,
            "label_table_fqn": config.label_fqn,
            "prediction_table_fqn": config.prediction_fqn,
            "registered_model_name": config.registered_model_name,
            "register_model": config.register_model,
            "prediction_threshold": config.prediction_threshold,
            "iterations": config.iterations,
            "learning_rate": config.learning_rate,
            "depth": config.depth,
            "numeric_feature_count": len(NUMERIC_FEATURES),
            "categorical_feature_count": len(CATEGORICAL_FEATURES),
            "categorical_features": json.dumps(CATEGORICAL_FEATURES),
        }
    )

    model.fit(train_pool, eval_set=valid_pool, use_best_model=True)

    valid_metrics = evaluate_classifier(
        model,
        valid_pool,
        valid_pd,
        config.prediction_threshold,
    )
    test_metrics = evaluate_classifier(
        model,
        test_pool,
        test_pd,
        config.prediction_threshold,
    )

    valid_confusion_matrix_pd = build_confusion_matrix(
        model,
        valid_pool,
        valid_pd,
        config.prediction_threshold,
    )
    test_confusion_matrix_pd = build_confusion_matrix(
        model,
        test_pool,
        test_pd,
        config.prediction_threshold,
    )
    feature_importance_pd = build_feature_importance(model, train_pool)
    scores_pd = make_scores(model, dataset_pd, config, run.info.run_id)

    mlflow.set_tags(
        {
            "project": "RetainFlow",
            "pipeline_stage": "churn_model_training",
            "model_family": "gradient_boosting",
            "model_library": "catboost",
            "data_source": "databricks_delta",
            "dataset_engine": "spark_to_pandas",
        }
    )

    for metric_name, metric_value in valid_metrics.items():
        mlflow.log_metric(f"valid_{metric_name}", metric_value)

    for metric_name, metric_value in test_metrics.items():
        mlflow.log_metric(f"test_{metric_name}", metric_value)

    mlflow.log_metric("dataset_rows", len(dataset_pd))
    mlflow.log_metric("train_rows", len(train_pd))
    mlflow.log_metric("valid_rows", len(valid_pd))
    mlflow.log_metric("test_rows", len(test_pd))
    mlflow.log_metric("scored_rows", len(scores_pd))
    mlflow.log_metric("positive_labels", int(dataset_pd["label"].sum()))
    mlflow.log_metric("negative_labels", int((dataset_pd["label"] == 0).sum()))
    mlflow.log_metric("global_churn_rate", float(dataset_pd["label"].mean()))
    mlflow.log_metric("avg_predicted_churn_probability", float(scores_pd["churn_probability"].mean()))
    mlflow.log_metric("max_predicted_churn_probability", float(scores_pd["churn_probability"].max()))
    mlflow.log_metric("min_predicted_churn_probability", float(scores_pd["churn_probability"].min()))

    log_churn_artifacts(
        config=config,
        dataset=dataset_pd,
        split_summary=split_summary,
        label_distribution=label_distribution_pd,
        feature_profile=feature_profile_pd,
        feature_importance=feature_importance_pd,
        valid_confusion_matrix=valid_confusion_matrix_pd,
        test_confusion_matrix=test_confusion_matrix_pd,
        scores=scores_pd,
    )

    log_model_kwargs = {
        "cb_model": model,
        "artifact_path": "model",
    }

    if config.register_model:
        log_model_kwargs["registered_model_name"] = config.registered_model_name

    mlflow.catboost.log_model(**log_model_kwargs)

    scoring_run_id = run.info.run_id

model_metrics = {
    "valid_metrics": valid_metrics,
    "test_metrics": test_metrics,
    "mlflow_run_id": scoring_run_id,
}

model_metrics

# COMMAND ----------

# MAGIC %md
# MAGIC ## 13. Matrices De Confusion
# MAGIC
# MAGIC Ces matrices sont affichées dans le notebook et loggées dans MLflow comme artifacts CSV.

# COMMAND ----------

display(spark.createDataFrame(valid_confusion_matrix_pd))

# COMMAND ----------

display(spark.createDataFrame(test_confusion_matrix_pd))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 14. Importance Des Variables
# MAGIC
# MAGIC On inspecte les variables les plus importantes pour comprendre ce que le modèle utilise.
# MAGIC Cette table est aussi loggée dans MLflow comme artifact.

# COMMAND ----------

display(spark.createDataFrame(feature_importance_pd))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 15. Scoring De Tous Les Clients
# MAGIC
# MAGIC On applique le modèle à tout le dataset pour produire une probabilité churn par client.

# COMMAND ----------

scores_pd = make_scores(model, dataset_pd, config, scoring_run_id)

scores_pd.head(10)

# COMMAND ----------

display(
    spark.createDataFrame(
        scores_pd.groupby("churn_risk_band", dropna=False)
        .agg(
            customers=("customer_id", "count"),
            avg_churn_probability=("churn_probability", "mean"),
        )
        .reset_index()
    )
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 16. Écriture Des Scores Dans Delta
# MAGIC
# MAGIC Les scores sont écrits dans la table configurée :
# MAGIC
# MAGIC `retainflow.ml.churn_predictions`

# COMMAND ----------

scores_spark = spark.createDataFrame(scores_pd)

(
    scores_spark.write.format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(config.prediction_fqn)
)

config.prediction_fqn

# COMMAND ----------

# MAGIC %md
# MAGIC ## 17. Validation De La Table De Prédictions
# MAGIC
# MAGIC On relit la table Delta finale pour vérifier ce qui a été réellement persisté.

# COMMAND ----------

predictions_spark = spark.table(config.prediction_fqn)

display(
    predictions_spark.groupBy("churn_risk_band")
    .agg(
        F.count("*").alias("customers"),
        F.round(F.avg("churn_probability"), 4).alias("avg_predicted_probability"),
        F.round(F.min("churn_probability"), 4).alias("min_probability"),
        F.round(F.max("churn_probability"), 4).alias("max_probability"),
    )
    .orderBy(F.desc("avg_predicted_probability"))
)

# COMMAND ----------

display(
    predictions_spark.orderBy(F.desc("churn_probability"))
    .limit(100)
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 18. Résumé Final
# MAGIC
# MAGIC Ce résumé permet de vérifier rapidement le run ML.

# COMMAND ----------

summary = {
    "config_path": str(CONFIG_PATH),
    "feature_table": config.feature_fqn,
    "label_table": config.label_fqn,
    "prediction_table": config.prediction_fqn,
    "mlflow_experiment": config.experiment_name,
    "mlflow_run_id": scoring_run_id,
    "train_rows": len(train_pd),
    "valid_rows": len(valid_pd),
    "test_rows": len(test_pd),
    "scored_rows": scores_spark.count(),
    "valid_metrics": valid_metrics,
    "test_metrics": test_metrics,
}

summary
