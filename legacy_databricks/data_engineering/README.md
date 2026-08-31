# RetainFlow - Data Engineering

Ce dossier contient la partie Data Engineering de la Phase 1 de RetainFlow.

L'objectif est de construire une vraie architecture de donnees assurance sur Databricks : Unity Catalog, schemas Medallion, tables Delta, donnees synthetiques coherentes et controles qualite.

## Lancer Le Pipeline

Commande recommandee pour un test rapide :

```bash
poetry run python data_engineering/run_phase1_pipeline.py --n-customers 1000
```

Si le test marche, relance avec le volume de developpement :

```bash
poetry run python data_engineering/run_phase1_pipeline.py --n-customers 10000
```

## Notebook D'Exploration SQL

Un notebook Databricks SQL est disponible pour visualiser les tables creees :

```text
notebooks/00_sql_explore_retainflow.sql
```

Pour l'importer dans Databricks Workspace :

```bash
databricks workspace import notebooks/00_sql_explore_retainflow.sql /Users/s239150.eps@gmail.com/RetainFlow/00_sql_explore_retainflow --format SOURCE --language SQL --overwrite --profile retainflow
```

Ensuite, ouvre le notebook dans Databricks :

```text
Workspace > Users > s239150.eps@gmail.com > RetainFlow > 00_sql_explore_retainflow
```

Ce notebook permet de tester des commandes SQL et de visualiser :

```text
schemas
tables
volumes
clients
contrats
evenements de contrats
paiements
relations logiques
audits de generation
```

Le pipeline utilise :

```text
profil Databricks : retainflow
SQL Warehouse     : DATABRICKS_SQL_WAREHOUSE_ID dans .env
catalog cible     : retainflow
```

Le pipeline fait automatiquement :

```text
1. creation du catalog, schemas et tables Delta
2. creation de la configuration de generation
3. remplissage des dimensions de reference
4. generation des clients
5. generation des contrats
6. generation des evenements de contrats
7. generation des paiements
8. generation des sinistres
9. generation des interactions et cas service client
10. generation des campagnes marketing et devis
11. generation des actions de retention
12. construction Gold Customer 360
13. construction des features et labels ML churn
14. ecriture des controles qualite dans monitoring.data_quality_results
15. controles clients
16. controles contrats
17. controles paiements
18. controles sinistres
19. controles interactions et service client
20. controles campagnes et devis
21. controles actions de retention
22. controles Customer 360
23. controles dataset ML churn
24. synthese des controles qualite
25. validation globale de l'architecture
```

## Architecture Cible

```text
retainflow
├── raw
├── bronze
├── silver
├── gold
├── ml
└── monitoring
```

Role des schemas :

```text
raw          zone de depot des donnees sources synthetiques imparfaites
bronze       donnees brutes ingerees avec metadonnees techniques
silver       modele entreprise propre, coherent et type
gold         tables analytiques et Customer 360
ml           futures features, labels, scores et sorties de modeles
monitoring   configuration, qualite, audit et suivi des generations
```

## Changer Le Volume

Le plus simple est de passer le volume au pipeline :

```bash
poetry run python data_engineering/run_phase1_pipeline.py --n-customers 1000
poetry run python data_engineering/run_phase1_pipeline.py --n-customers 10000
poetry run python data_engineering/run_phase1_pipeline.py --n-customers 100000
```

Progression recommandee :

```text
1000      smoke test rapide
10000     developpement normal
100000    gros volume quand toutes les facts sont stables
```

Tu peux aussi modifier la valeur par defaut dans :

```text
00_set_generation_config.sql
```

Ligne a changer :

```sql
10000 AS n_customers
```

## Scripts SQL

```text
00_define_uc_model.sql
```

Cree le catalog `retainflow`, les schemas, les tables Delta, les commentaires et les relations logiques.

```text
00_set_generation_config.sql
```

Definit la configuration active de generation.

```text
02_seed_reference_dimensions.sql
```

Remplit :

```text
silver.dim_date
silver.dim_channel
silver.dim_product
silver.dim_geography
silver.dim_agent
```

```text
03_generate_customers.sql
```

Genere `silver.dim_customer`.

```text
05_generate_policies.sql
```

Genere :

```text
silver.fact_policy
silver.fact_policy_events
```

```text
07_generate_payments.sql
```

Genere `silver.fact_payments`.

```text
09_generate_claims.sql
```

Genere `silver.fact_claims`.

```text
11_generate_interactions_service.sql
```

Genere :

```text
silver.fact_interactions
silver.fact_customer_service
```

```text
13_generate_marketing_quotes.sql
```

Genere :

```text
silver.fact_campaign_contact
silver.fact_quotes
```

```text
15_generate_retention_actions.sql
```

Genere `silver.fact_retention_actions`.

```text
17_build_gold_customer_360.sql
```

Construit `gold.customer_360_snapshot`.

```text
20_define_ml_model.sql
```

Garantit que le schema `ml` et les tables ML existent avant la generation du dataset churn.

```text
21_build_ml_churn_dataset.sql
```

Construit :

```text
ml.churn_feature_snapshot
ml.churn_labels
ml.churn_predictions
```

```text
19_run_data_quality_checks.sql
```

Execute les controles qualite principaux et ecrit les resultats dans `monitoring.data_quality_results`.

## Scripts De Verification

```text
01_verify_uc_model.sql
04_verify_customer_generation.sql
06_verify_policy_generation.sql
08_verify_payment_generation.sql
10_verify_claim_generation.sql
12_verify_interactions_service_generation.sql
14_verify_marketing_quote_generation.sql
16_verify_retention_action_generation.sql
18_verify_gold_customer_360.sql
22_verify_ml_churn_dataset.sql
20_verify_data_quality_results.sql
99_validate_data_architecture.sql
```

Le script le plus utile pour verifier l'etat global est :

```text
99_validate_data_architecture.sql
```

Il confirme :

```text
schemas attendus
tables attendues
configuration active
volumes par table
dernieres generations
```

## Resultats Attendus

Pour `--n-customers 10000`, tu dois obtenir environ :

```text
silver.dim_date              2191
silver.dim_channel           9
silver.dim_product           21
silver.dim_geography         24
silver.dim_agent             240
silver.dim_customer          10000
silver.fact_policy           16000 a 19000
silver.fact_policy_events    plusieurs evenements par contrat
silver.fact_payments         plusieurs paiements par contrat
silver.fact_claims           sinistres correles aux contrats et produits
silver.fact_interactions     interactions clients multicanales
silver.fact_customer_service cas service issus des interactions
silver.fact_campaign_contact expositions marketing et conversion
silver.fact_quotes           devis et pression concurrentielle
silver.fact_retention_actions actions de retention historiques
gold.customer_360_snapshot   vue analytique client 360
gold.retention_priority_queue recommandations retention apres scoring ML
ml.churn_feature_snapshot    features pretes pour le churn
ml.churn_labels              labels churn synthetiques
ml.churn_predictions         scores churn produits par le modele
monitoring.logical_relationships 18
monitoring.data_quality_results controles qualite persistants
```

Les controles importants doivent rester a `0` :

```text
duplicate_customer_id_count
duplicate_policy_id_count
duplicate_policy_event_id_count
duplicate_payment_id_count
orphan_geography_count
orphan_acquisition_channel_count
orphan_preferred_channel_count
orphan_policy_customer_count
orphan_policy_product_count
orphan_policy_channel_count
orphan_policy_agent_count
orphan_event_policy_count
orphan_payment_policy_count
orphan_payment_customer_count
invalid_policy_date_count
invalid_cancellation_date_count
payment_outside_policy_period_count
non_positive_payment_amount_count
duplicate_claim_id_count
orphan_claim_policy_count
orphan_claim_customer_count
orphan_claim_product_count
claim_outside_policy_period_count
non_positive_claim_amount_count
negative_paid_amount_count
paid_above_claim_amount_count
duplicate_interaction_id_count
duplicate_case_id_count
orphan_interaction_customer_count
orphan_interaction_policy_count
orphan_interaction_channel_count
orphan_interaction_agent_count
orphan_case_interaction_count
orphan_case_customer_count
non_positive_duration_count
invalid_sentiment_count
close_before_open_count
invalid_satisfaction_count
duplicate_campaign_contact_id_count
duplicate_quote_id_count
orphan_campaign_customer_count
orphan_campaign_channel_count
orphan_quote_customer_count
orphan_quote_product_count
orphan_quote_channel_count
orphan_quote_agent_count
non_positive_quote_amount_count
invalid_competitor_price_index_count
duplicate_retention_action_id_count
orphan_retention_customer_count
orphan_retention_policy_count
orphan_retention_channel_count
orphan_retention_agent_count
negative_offered_value_count
invalid_action_type_count
invalid_trigger_reason_count
duplicate_customer_360_count
orphan_customer_360_count
negative_tenure_count
invalid_email_open_rate_count
invalid_satisfaction_score_count
invalid_churn_risk_band_count
duplicate_feature_key_count
duplicate_label_key_count
orphan_feature_customer_count
orphan_label_customer_count
missing_label_for_feature_count
missing_feature_for_label_count
invalid_churn_label_count
invalid_churn_probability_count
```

La couche `ml` consomme la couche `gold`, pas directement toutes les tables transactionnelles. L'idee est de garder une architecture propre : Silver porte les faits et dimensions, Gold porte la vision client analytique, puis ML construit les features et les labels churn a partir de cette vision consolidee.

## Execution Manuelle

Si tu veux executer les fichiers un par un dans Databricks SQL Editor :

```text
1. 00_define_uc_model.sql
2. 00_set_generation_config.sql
3. 02_seed_reference_dimensions.sql
4. 03_generate_customers.sql
5. 04_verify_customer_generation.sql
6. 05_generate_policies.sql
7. 06_verify_policy_generation.sql
8. 07_generate_payments.sql
9. 08_verify_payment_generation.sql
10. 09_generate_claims.sql
11. 10_verify_claim_generation.sql
12. 11_generate_interactions_service.sql
13. 12_verify_interactions_service_generation.sql
14. 13_generate_marketing_quotes.sql
15. 14_verify_marketing_quote_generation.sql
16. 15_generate_retention_actions.sql
17. 16_verify_retention_action_generation.sql
18. 17_build_gold_customer_360.sql
19. 18_verify_gold_customer_360.sql
20. 20_define_ml_model.sql
21. 21_build_ml_churn_dataset.sql
22. 22_verify_ml_churn_dataset.sql
23. 19_run_data_quality_checks.sql
24. 20_verify_data_quality_results.sql
25. 99_validate_data_architecture.sql
```

## Etat Actuel

Le pipeline Phase 1 construit maintenant :

```text
Unity Catalog retainflow
schemas raw, bronze, silver, gold, ml, monitoring
dimensions de reference
clients synthetiques
contrats
evenements de contrats
paiements
sinistres
interactions
cas service client
campagnes marketing
devis
actions de retention
customer 360 gold
features et labels ML churn
resultats de qualite persistants
controles de validation
```

Prochaine etape data : creer un premier entrainement MLflow sur le dataset churn.
