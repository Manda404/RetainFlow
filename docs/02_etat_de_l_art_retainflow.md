# RetainFlow - Etat Actuel

## Positionnement

RetainFlow repart sur une base PostgreSQL locale pour simuler un systeme d'information assurance francais. L'objectif immediat est d'avoir une base relationnelle riche, interrogeable, et assez realiste pour entrainer ensuite un modele de churn.

## Ce Qui Est Actif

```text
docker-compose.yml
sql/postgres/00_schema.sql
src/retainflow/generation/synthetic.py
src/retainflow/data/csv_etl.py
src/retainflow/pipelines/build_dataset.py
notebooks/00_postgres_bootstrap_retainflow.py
config/data_pipeline.yml
src/retainflow/
logs/retainflow.log
```

## Ce Qui Est Archive

Les fichiers de creation/orchestration Databricks ont ete deplaces dans:

```text
legacy_databricks/
```

Ils ne sont plus le chemin recommande pour creer les tables ou generer les donnees.

## Donnees Creees

Le generateur produit d'abord des CSV, puis l'ETL les charge dans PostgreSQL:

```text
clients
agences francaises
conseillers
produits assurance
contrats
evenements contrat
paiements
sinistres
interactions
cas service client
campagnes
devis
actions de retention
snapshots Customer 360
labels churn
```

Les CSV ont des valeurs manquantes controlees sur des champs plausibles: telephone, conseiller optionnel, dates de fermeture, satisfaction, renouvellement, etc.

## Prochaine Etape

Migrer le modele churn vers PostgreSQL:

```text
1. lecture SQL des snapshots et labels depuis PostgreSQL
2. split temporel train / validation / test / backtest
3. entrainement local CatBoost
4. tracking MLflow local
5. predictions en table PostgreSQL
6. explicabilite SHAP pour chaque run
```
