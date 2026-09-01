# RetainFlow - Architecture Donnees PostgreSQL

## Decision

La base operationnelle RetainFlow est maintenant PostgreSQL local. Databricks n'est plus utilise pour creer les tables ni alimenter les donnees de depart.

## Objectif Metier

RetainFlow simule un systeme d'information assurance en France, avec des agences regionales, des conseillers, des clients, des contrats, des paiements, des sinistres, des interactions, des campagnes et des actions de retention.

Cette base sert ensuite a trois usages:

- entrainer un modele de churn;
- interroger les donnees avec un agent SQL;
- envoyer des profils client au modele, puis retourner prediction + explicabilite SHAP + signaux metier.

## Socle Technique

```text
PostgreSQL 16 via Docker
schema SQL: sql/postgres/00_schema.sql
generation metier: src/retainflow/generation/synthetic.py
generation CSV + ETL: src/retainflow/data/csv_etl.py
orchestrateur CLI: src/retainflow/pipelines/build_dataset.py
notebook bootstrap: notebooks/00_postgres_bootstrap_retainflow.ipynb
notebook ML: notebooks/01_train_churn_catboost.ipynb
code ML: src/retainflow/modeling/
logs: logs/retainflow.log
port local: 55432
dsn: postgresql://retainflow:retainflow@localhost:55432/retainflow
```

## Modele Relationnel

```text
dim_date
dim_geography
dim_agency
dim_channel
dim_agent
dim_product
dim_customer
fact_policy
fact_policy_event
fact_payment
fact_claim
fact_interaction
fact_customer_service
fact_campaign_contact
fact_quote
fact_retention_action
customer_360_snapshot
churn_label
generation_batch
```

Les cles etrangeres sont materialisees dans PostgreSQL. L'agent SQL pourra donc s'appuyer sur un vrai graphe relationnel au lieu de deviner les jointures.

## Periode Et Splits

Les donnees couvrent l'historique du 1 janvier 2020 au 30 juin 2026.

```text
train       observations 2021-12-31, 2022-12-31, 2023-12-31
validation observation  2024-12-31
test        observation  2025-12-31
backtest    observation  2026-06-30
```

Chaque client obtient plusieurs snapshots analytiques dans `customer_360_snapshot` et des labels supervises dans `churn_label`.

## Realisme Des Donnees

Le generateur encode des effets metier coherents:

- la zone geographique influence revenu, adoption digitale et risque sinistre;
- les agences sont rattachees a des villes francaises et portent les conseillers;
- les clients ont des scores latents de sensibilite prix, service, digital, fidelite et sinistre;
- les contrats ont primes, remises, augmentations, renouvellements et annulations;
- les paiements creent des incidents selon revenu et sensibilite prix;
- les sinistres influencent satisfaction et interactions;
- les reclamations et SLA degradent le risque churn;
- les actions retention gardent un historique d'offre, acceptation et retention a 90 jours.

## Flux CSV Puis ETL

La generation n'insere pas directement les donnees dans PostgreSQL.

```text
generate_csv_dataset(output_dir, n_customers, seed)
  -> ecrit un fichier CSV par table

load_csv_dataset_to_postgres(input_dir, dsn, reset)
  -> charge les fichiers dans PostgreSQL dans l'ordre des relations
```

Les CSV representent une source plus realiste que des tables parfaites: certains champs optionnels sont manquants et le preprocessing ML doit savoir les traiter.

## Premiere Requete De Controle

```sql
SELECT split_name, count(*) AS rows, avg(churn_label) AS churn_rate
FROM retainflow.churn_label
GROUP BY split_name
ORDER BY split_name;
```
