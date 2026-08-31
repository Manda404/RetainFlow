# RetainFlow - Orchestration Databricks Jobs

## Objectif

Cette etape transforme le projet en workflow Databricks orchestrable.

Au lieu de lancer chaque notebook manuellement, on definit un job end-to-end :

```text
phase1_data_pipeline
  -> train_churn_model
  -> build_retention_priority_queue
  -> run_monitoring_dashboard_checks
```

## Fichiers Ajoutes

```text
databricks.yml
resources/retainflow_jobs.yml
data_engineering/23_run_phase1_pipeline_databricks.py
config/data_pipeline.yml
```

## Configuration Data Pipeline

La configuration du pipeline Databricks-native est ici :

```text
config/data_pipeline.yml
```

Exemple :

```yaml
n_customers: 10000
history_start_date: "2021-01-01"
history_end_date: "2025-12-31"
snapshot_date: "2025-12-31"
prediction_horizon_days: 90
```

Pour tester avec moins de volume, change :

```yaml
n_customers: 1000
```

Puis reimporte les fichiers :

```bash
poetry run python scripts/import_databricks_notebooks.py
```

## Import Des Notebooks Et Fichiers

Avant de lancer le job, importe tous les notebooks, fichiers SQL, fichiers YAML et modules Python :

```bash
poetry run python scripts/import_databricks_notebooks.py
```

Cette commande envoie notamment :

```text
config/data_pipeline.yml
config/churn_model.yml
retainflow/config.py
retainflow/churn.py
data_engineering/*.sql
data_engineering/23_run_phase1_pipeline_databricks.py
churn_model/01_train_churn_model.py
retention_engine/01_build_retention_priority_queue.py
monitoring/01_monitoring_dashboard.sql
```

## Workflow Databricks Bundle

Le job est defini ici :

```text
resources/retainflow_jobs.yml
```

Il utilise la variable :

```text
cluster_id
```

Tu dois fournir l'identifiant d'un cluster Databricks existant.

## Validation Du Bundle

Commande :

```bash
databricks bundle validate --var cluster_id=<TON_CLUSTER_ID> --profile retainflow
```

## Deploiement Du Job

Commande :

```bash
databricks bundle deploy --var cluster_id=<TON_CLUSTER_ID> --profile retainflow
```

## Lancement Du Workflow

Commande :

```bash
databricks bundle run retainflow_end_to_end_workflow --var cluster_id=<TON_CLUSTER_ID> --profile retainflow
```

## Ordre Des Taches

### 1. `phase1_data_pipeline`

Execute :

```text
data_engineering/23_run_phase1_pipeline_databricks.py
```

Cette tache :

```text
lit config/data_pipeline.yml
cree ou met a jour le catalog et les schemas
cree les tables Delta
genere les donnees Silver
construit Gold Customer 360
construit les tables ML features/labels
execute les controles qualite
execute les validations
```

### 2. `train_churn_model`

Execute :

```text
churn_model/01_train_churn_model.py
```

Cette tache :

```text
lit config/churn_model.yml
lit retainflow.ml.churn_feature_snapshot
lit retainflow.ml.churn_labels
convertit Spark vers Pandas avec toPandas()
entraine CatBoost
logge tout dans MLflow Databricks
ecrit retainflow.ml.churn_predictions
```

### 3. `build_retention_priority_queue`

Execute :

```text
retention_engine/01_build_retention_priority_queue.py
```

Cette tache :

```text
lit les predictions churn
calcule un priority_score
choisit une action recommandee
choisit un canal recommande
ecrit retainflow.gold.retention_priority_queue
```

### 4. `run_monitoring_dashboard_checks`

Execute :

```text
monitoring/01_monitoring_dashboard.sql
```

Cette tache :

```text
verifie les volumes
verifie les resultats DQ
verifie les scores churn
verifie la queue retention
donne une vision de bout en bout
```

## Pourquoi Cette Etape Est Importante

Cette etape fait passer RetainFlow de :

```text
notebooks lances manuellement
```

a :

```text
workflow Databricks end-to-end deployable
```

C'est le debut de l'industrialisation MLOps.

## Suite Recommandee

Apres cette etape, les prochaines ameliorations sont :

```text
ajouter un job schedule
ajouter des alertes si data_quality_results contient des FAIL
ajouter des tests d'integration Databricks
ajouter une validation ML avant ecriture des predictions
activer le Model Registry quand les permissions Unity Catalog sont pretes
ajouter monitoring de drift
```
