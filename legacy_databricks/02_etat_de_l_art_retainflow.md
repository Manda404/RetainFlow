# RetainFlow - Etat De L'Art Du Projet

## 1. Objectif Du Projet

RetainFlow est une plateforme Data, Machine Learning et decisionnelle sur Databricks pour simuler un cas assurance realiste autour de la retention client.

L'objectif n'est pas seulement de generer des donnees synthetiques. Le projet vise a construire une chaine complete :

```text
Data Engineering -> Customer 360 -> Feature Engineering -> ML Churn -> Scoring -> Retention Engine -> Dashboards -> Monitoring
```

Le cas metier cible est le suivant :

```text
identifier les clients avec risque de churn
comprendre les facteurs de risque
prioriser les clients a traiter
recommander une action de retention
suivre la qualite des donnees et des scores
preparer une future couche agentique
```

## 2. Etat Actuel Du Projet

Le projet contient deja une base solide couvrant les premieres briques d'une plateforme moderne.

```text
RetainFlow
├── data_engineering
├── churn_model
├── retention_engine
├── monitoring
├── notebooks
├── config
├── retainflow
├── scripts
├── tests
└── docs
```

### Briques Deja Construites

| Brique | Statut | Description |
| --- | --- | --- |
| Unity Catalog | En place | Catalog `retainflow`, schemas Medallion et monitoring. |
| Modele de donnees | En place | Tables Delta Silver, Gold, ML et Monitoring. |
| Generation synthetique | En place | Donnees assurance coherentes et parametrables par volume. |
| Pipeline Data Engineering | En place | Execution automatisee des scripts SQL avec Databricks SQL Warehouse. |
| Data Quality | En place | Controles persistants dans `monitoring.data_quality_results`. |
| Customer 360 | En place | Table Gold analytique client. |
| Dataset ML churn | En place | Features et labels dans le schema `ml`. |
| Modele churn | En place | CatBoost avec conversion Spark vers Pandas. |
| MLflow | En place | Logging complet des parametres, metriques, artifacts et modele. |
| Retention Engine | En place | Queue de recommandations retention dans Gold. |
| Dashboards SQL | En place | Exploration, retention et monitoring. |
| Configuration YAML | En place | Configuration du modele dans `config/churn_model.yml`. |
| Package Python | En place | Code reutilisable dans `retainflow/`. |
| Tests | Debut | Test de chargement de configuration. |
| Orchestration Jobs | En place V1 | Databricks Asset Bundle avec workflow end-to-end parametre par `cluster_id`. |

## 3. Architecture Data

L'architecture repose sur Databricks, Unity Catalog et Delta Lake.

```text
retainflow
├── raw
├── bronze
├── silver
├── gold
├── ml
└── monitoring
```

### Role Des Schemas

| Schema | Role | Etat |
| --- | --- | --- |
| `raw` | Zone de depot source | Reserve pour futures donnees brutes. |
| `bronze` | Ingestion brute historisee | Reserve pour future ingestion incrementalisee. |
| `silver` | Modele entreprise propre | Actif. Dimensions et faits assurance. |
| `gold` | Tables analytiques metier | Actif. Customer 360 et retention queue. |
| `ml` | Features, labels et predictions | Actif. Dataset churn et scores. |
| `monitoring` | Qualite, configuration, audit | Actif. DQ, batches et relations logiques. |

### Evaluation

Le projet suit une approche Medallion correcte :

```text
Silver = donnees propres et coherentes
Gold = donnees analytiques orientees usage
ML = donnees specialisees pour entrainement et scoring
Monitoring = observabilite data et pipeline
```

Point positif : les tables ML ne lisent pas toutes les tables transactionnelles directement. Elles consomment principalement la couche Gold, ce qui evite de melanger logique analytique et logique de modele.

Point a ameliorer : les schemas `raw` et `bronze` sont definis mais pas encore pleinement exploites. Pour un projet plus proche production, il faudra ajouter ingestion, historisation, schema evolution et traitement incremental.

## 4. Modele De Donnees

Le modele actuel couvre les principaux objets assurance necessaires au churn :

```text
clients
geographie
canaux
agents
produits
contrats
evenements de contrats
paiements
sinistres
interactions
service client
campagnes marketing
devis
actions de retention historiques
```

### Tables Principales

| Couche | Tables |
| --- | --- |
| Silver dimensions | `dim_customer`, `dim_product`, `dim_channel`, `dim_agent`, `dim_geography`, `dim_date` |
| Silver facts | `fact_policy`, `fact_policy_events`, `fact_payments`, `fact_claims`, `fact_interactions`, `fact_customer_service`, `fact_campaign_contact`, `fact_quotes`, `fact_retention_actions` |
| Gold | `customer_360_snapshot`, `retention_priority_queue` |
| ML | `churn_feature_snapshot`, `churn_labels`, `churn_predictions` |
| Monitoring | `generation_config`, `generation_batches`, `data_quality_results`, `logical_relationships` |

### Evaluation

Le modele est riche pour un projet churn, car il ne reduit pas le churn a une seule table client. Les signaux viennent de plusieurs domaines :

```text
contrat
prix
paiement
sinistre
service client
engagement digital
marketing
renouvellement
historique retention
```

Cette structure est proche d'un vrai cas entreprise.

## 5. Generation De Donnees

La generation actuelle est controlee par configuration :

```bash
poetry run python data_engineering/run_phase1_pipeline.py --n-customers 1000
poetry run python data_engineering/run_phase1_pipeline.py --n-customers 10000
```

Le pipeline met a jour `monitoring.generation_config`, puis execute les scripts SQL dans le bon ordre.

### Points Forts

```text
volume configurable
donnees relationnelles coherentes
relations logiques documentees
historique de generation
controles qualite persistants
validation globale de l'architecture
```

### Limites

```text
pas encore de raw/bronze reel
pas encore de generation incrementalisee
pas encore de late arriving data
pas encore de schema drift simule
pas encore de versioning de dataset ML
```

## 6. Data Quality Et Monitoring

Le projet a deja une vraie table de qualite :

```text
retainflow.monitoring.data_quality_results
```

Les controles couvrent :

```text
row counts
unicite des cles
orphelins entre tables
coherence des montants
coherence des dates
bornes de scores
coherence features/labels
coherence predictions/recommendations
```

### Evaluation

C'est un bon niveau pour un projet d'apprentissage avance. La qualite n'est pas seulement affichee dans un notebook, elle est persistee dans une table de monitoring.

Point a ameliorer : ajouter des seuils parametrables et un statut pipeline bloquant si un controle critique echoue.

## 7. Feature Engineering

Le projet construit une table Gold :

```text
retainflow.gold.customer_360_snapshot
```

Puis une table ML :

```text
retainflow.ml.churn_feature_snapshot
```

Les features incluent :

```text
tenure_months
active_policy_count
number_of_products
total_annual_premium
total_claims_12m
payment_incidents_6m
complaints_6m
interactions_3m
days_since_last_contact
digital_sessions_30d
email_open_rate_6m
premium_increase_pct_max_12m
avg_satisfaction_score_12m
renewal_days_min
customer_value_score
customer_segment
estimated_income_band
digital_profile
price_sensitivity_score
digital_engagement_score
loyalty_score
```

### Evaluation

Le feature engineering est coherent avec un cas churn assurance. Les signaux couvrent comportement, valeur client, satisfaction, prix, renouvellement, engagement et historique relationnel.

Point a ameliorer : creer une vraie logique point-in-time stricte et documentee pour eviter toute fuite de donnees dans un contexte production.

## 8. Machine Learning

Le modele actuel utilise :

```text
CatBoostClassifier
Spark pour lire/ecrire Delta
toPandas() pour construire le dataset Pandas
MLflow Databricks pour tracker le run
```

### Pourquoi CatBoost

CatBoost est un bon choix pour ce projet car :

```text
il gere bien les donnees tabulaires
il gere nativement les variables categorielles
il demande moins de preprocessing qu'un modele lineaire
il est performant sur des datasets metier structures
il donne une importance des variables interpretable
```

### Structure Projet

La logique ML est separee :

```text
config/churn_model.yml      configuration du modele
retainflow/config.py        chargement typé YAML
retainflow/churn.py         preparation, training, evaluation, scoring, MLflow
churn_model/01_train_churn_model.py notebook detaille Databricks
```

Le notebook montre toutes les etapes, mais le code reutilisable vit dans le package `retainflow`.

### Logging MLflow

Le run MLflow logge :

```text
configuration YAML
tables source et cible
tags projet/stage/modele
features numeriques et categorielles
metriques validation/test
AUC
average precision
accuracy
F1
precision
recall
volumes dataset/train/validation/test/scoring
taux churn global
distribution des labels
profil statistique des features
matrices de confusion
importance des variables
sample training dataset
sample predictions
modele CatBoost
```

### Evaluation

Le niveau actuel est correct pour une premiere version Data Science. On a :

```text
configuration externe
code package
notebook explicatif
tracking MLflow
artifacts
scoring Delta
tests de config
```

Points a ameliorer :

```text
ajouter calibration du score
ajouter courbes ROC/PR en artifacts image
ajouter evaluation par segment client
ajouter validation temporelle
ajouter model registry en mode production quand les permissions UC sont pretes
ajouter inference batch automatisee via job
```

## 9. Retention Engine

Le moteur de retention lit :

```text
retainflow.ml.churn_predictions
retainflow.gold.customer_360_snapshot
retainflow.silver.dim_channel
```

Il ecrit :

```text
retainflow.gold.retention_priority_queue
```

Cette table contient :

```text
recommendation_id
customer_id
churn_probability
priority_score
priority_tier
recommended_action_type
action_reason
recommended_channel_name
estimated_offer_value
scoring_run_id
```

### Evaluation

C'est une bonne premiere brique decisionnelle. Le projet ne s'arrete pas a la prediction : il transforme le score en action.

Point a ameliorer : remplacer progressivement les regles fixes par un moteur next-best-action plus avance, avec cout, probabilite d'acceptation, valeur client et uplift attendu.

## 10. Dashboards

Trois notebooks SQL existent :

```text
notebooks/00_sql_explore_retainflow.sql
notebooks/02_retention_dashboard.sql
monitoring/01_monitoring_dashboard.sql
```

Ils permettent de visualiser :

```text
tables creees
volumes
qualite data
scores churn
clients prioritaires
budget retention
recommandations par action/canal
monitoring de bout en bout
```

### Evaluation

Les notebooks SQL sont utiles pour l'exploration et le pilotage. Pour un projet plus mature, il faudra migrer les visualisations principales vers des dashboards Databricks SQL sauvegardes et partageables.

## 11. MLOps

Le projet commence a appliquer de bonnes pratiques MLOps :

```text
configuration externe YAML
package Python reutilisable
MLflow tracking
artifacts
table de predictions
monitoring SQL
tests unitaires
script d'import Databricks
Databricks Asset Bundle
workflow Jobs end-to-end
```

### Manques Actuels

```text
pas encore de Model Registry complet active par defaut
pas encore de promotion dev/stg/prd
pas encore de tests d'integration Databricks
pas encore de detection drift/data drift/model drift
pas encore de CI/CD
pas encore de schedule et alertes sur le job Databricks
```

## 12. Niveau De Maturite Actuel

| Domaine | Niveau | Commentaire |
| --- | --- | --- |
| Data Architecture | Bon | Medallion + UC + tables coherentes. |
| Data Generation | Bon | Donnees coherentes et volume configurable. |
| Data Quality | Bon | Resultats persistants et controles larges. |
| Feature Engineering | Moyen+ | Bonne base, point-in-time a renforcer. |
| ML Modeling | Bon pour V1 | CatBoost, Pandas, MLflow, artifacts. |
| MLOps | Moyen+ | Tracking en place, orchestration Jobs/Bundles V1 ajoutee. |
| Monitoring | Moyen+ | Notebooks SQL en place, drift a ajouter. |
| Retention Decisioning | Moyen | Regles utiles, uplift/optimisation a venir. |
| Agentic Layer | Non demarre | Dossier reserve, architecture prete. |

## 13. Risques Techniques

### Risque 1 - `toPandas()` Et Volume

`toPandas()` est acceptable pour les volumes actuels de developpement. Mais pour de gros volumes, le dataset doit tenir en memoire driver.

Mitigation :

```text
limiter n_customers en experimentation
echantillonner pour training
garder scoring Spark si besoin
passer a une strategie distribuee pour gros volumes
```

### Risque 2 - Labels Synthetiques

Les labels churn sont synthetiques. Le modele apprend donc la logique de simulation, pas encore un comportement reel.

Mitigation :

```text
documenter la generation des labels
creer plusieurs scenarios de churn
comparer modeles sur scenarios
preparer une future ingestion de labels reels
```

### Risque 3 - Fuite De Donnees

Un projet churn doit etre strict sur le point-in-time. Les features ne doivent jamais utiliser de donnees posterieures a `observation_date`.

Mitigation :

```text
formaliser les fenetres temporelles
tester les dates max par feature
ajouter des controles anti-leakage
versionner les snapshots
```

### Risque 4 - Recommandations Trop Reglees

La queue retention est basee sur des regles. C'est bien pour V1, mais pas suffisant pour optimiser la valeur.

Mitigation :

```text
ajouter uplift modeling
ajouter cout des actions
ajouter probabilite d'acceptation
ajouter expected retained value
```

## 14. Prochaine Roadmap Recommandee

### Phase 2 - Industrialisation MLOps

```text
stabiliser Databricks Jobs pour orchestrer pipeline data, training, scoring et retention
ajouter un schedule et des alertes sur le job Databricks
activer Model Registry si les permissions Unity Catalog sont disponibles
ajouter evaluation par segment client
ajouter courbes ROC et Precision-Recall dans MLflow
ajouter tests unitaires sur feature engineering et scoring
```

### Phase 3 - Monitoring ML

```text
drift des features
drift des scores
stabilite des distributions
monitoring par segment client
comparaison runs MLflow
alertes qualite
```

### Phase 4 - Retention Avancee

```text
next-best-action
uplift modeling
optimisation budget
simulation de campagnes
mesure ROI retention
```

### Phase 5 - Agentic Layer

```text
agent SQL gouverne
agent d'analyse retention
agent de recommandation action
explication client-level
guardrails sur tables autorisees
audit des reponses
```

## 15. Conclusion

RetainFlow est deja au-dela d'un simple projet de generation de donnees. Le projet contient maintenant une vraie base de plateforme Data/ML sur Databricks :

```text
architecture Medallion
Unity Catalog
modele assurance relationnel
pipeline SQL reproductible
data quality persistante
Customer 360
dataset ML
CatBoost
MLflow Databricks
scoring Delta
queue de retention
dashboards SQL
monitoring
configuration YAML
package Python
tests
```

Le prochain saut de maturite consiste a passer d'une execution manuelle via notebooks a une orchestration Databricks Jobs/Bundles, puis a ajouter le monitoring ML et l'optimisation des actions de retention.
