# RetainFlow

RetainFlow est un projet data science et agentique autour d'une question métier simple :

> Quels clients risquent de résilier leur contrat d'assurance, pourquoi, et quelles actions concrètes un conseiller peut-il engager pour les retenir ?

Le projet met en place une chaîne complète : une base PostgreSQL locale, un modèle de churn, de l'explicabilité, des recommandations de rétention et une interface agentique pour interroger le système en langage naturel.

L'objectif n'est pas seulement de produire un score. L'objectif est d'aider un conseiller, un gestionnaire ou une équipe métier à comprendre les clients prioritaires, à justifier les décisions et à choisir une action adaptée.

## Problématique

Dans une compagnie d'assurance, une résiliation est rarement causée par un seul événement. Elle peut venir d'une hausse de prime, d'un sinistre mal vécu, d'un paiement rejeté, d'une faible interaction avec l'agence, d'une pression concurrentielle ou d'un manque de réponse commerciale.

RetainFlow cherche donc à répondre à ces questions :

- quels clients présentent le plus fort risque de churn ;
- quels signaux expliquent ce risque ;
- quelles agences, régions ou segments sont les plus exposés ;
- quelles actions de rétention sont les plus pertinentes ;
- comment rendre les résultats compréhensibles pour un utilisateur métier.

## Vision Du Projet

Un utilisateur métier doit pouvoir poser une question naturelle, par exemple :

```text
Quels sont les 5 clients à contacter en urgence et pourquoi ?
```

RetainFlow doit alors :

1. comprendre l'intention de la question ;
2. interroger PostgreSQL si des données sont nécessaires ;
3. récupérer les clients prioritaires ;
4. exploiter les prédictions du modèle de churn ;
5. ajouter les explications SHAP disponibles ;
6. consulter les documents de stratégie marketing si besoin ;
7. retourner une réponse claire, avec tableau, graphique ou brouillon d'email.

## Ce Que Contient RetainFlow

**Une base de données assurance**

La base PostgreSQL locale représente un système d'information assurance centré sur la France : clients, agences, conseillers, contrats, produits, paiements, sinistres, interactions, campagnes marketing, devis concurrents et actions de rétention.

**Un modèle de churn**

Le modèle actuel utilise CatBoost. Le pipeline prend en compte le split temporel, le drift, le data leakage, le preprocessing, le feature engineering, l'entraînement, l'évaluation, le seuil de décision et le suivi MLflow.

**Une couche d'explicabilité**

Les rapports SHAP permettent d'expliquer les facteurs qui influencent les prédictions. L'idée est de répondre à la question : pourquoi ce client est-il considéré à risque ?

**Des recommandations métier**

RetainFlow construit une file de clients prioritaires et propose des actions de rétention lisibles : canal recommandé, justification, prochaine action et brouillon de message.

**Des agents**

La couche agentique transforme le projet en assistant interactif. Les agents peuvent interroger SQL, produire des KPI, rechercher dans les documents marketing, générer des graphiques, expliquer une prédiction ou rédiger un email.

## Architecture Simplifiée

```text
Utilisateur métier
        |
        v
Interface web RetainFlow
        |
        v
API locale FastAPI
        |
        v
Supervisor Agent
        |
        +--> SQL / KPI Agent --------> PostgreSQL
        |
        +--> Retention Advisor ------> prédictions churn
        |
        +--> Explainability Agent ---> rapports SHAP
        |
        +--> Strategy RAG Agent -----> documents marketing
        |
        +--> Visualization Agent ----> graphiques Plotly
        |
        +--> Email Agent ------------> brouillons de message
```

## Structure Du Projet

```text
RetainFlow/
├── app/                  interface web locale
├── config/               configuration YAML
├── data/                 données raw, processed et documents RAG
├── docs/                 documentation du projet
├── logs/                 logs locaux du projet
├── notebooks/            notebooks étape par étape
├── reports/              tableaux, figures et rapports générés
├── scripts/              scripts utilitaires
├── sql/                  schéma PostgreSQL
├── src/retainflow/       code Python de production
└── tests/                tests automatisés
```

Les dossiers historiques ou non essentiels ont été retirés afin de garder une architecture plus claire.

## Parcours Des Notebooks

Les notebooks sont pensés pour être exécutés dans l'ordre.

```text
00_postgres_bootstrap_retainflow.ipynb
```

Crée les CSV, prépare la base et alimente PostgreSQL.

```text
01_train_churn_catboost.ipynb
```

Charge les données, analyse le drift et le leakage, entraîne CatBoost, évalue le modèle, log dans MLflow et sauvegarde les prédictions.

```text
02_churn_drift_dashboard.ipynb
```

Étudie le drift entre train, validation, test et backtest.

```text
03_retention_priority_queue.ipynb
```

Construit la liste des clients à traiter en priorité.

```text
04_retention_strategy_recommendations.ipynb
```

Produit des recommandations de rétention exploitables par le métier.

```text
05_agentic_retention_workflow.ipynb
```

Montre comment utiliser les agents RetainFlow depuis Python.

## Interface Agentique

RetainFlow propose une interface web locale pour tester les agents.

Elle permet de :

- poser une question métier ;
- afficher une réponse structurée ;
- consulter les lignes SQL retournées ;
- voir les métadonnées de raisonnement ;
- afficher des graphiques Plotly ;
- obtenir des brouillons de message ;
- suivre les agents mobilisés dans le workflow.

## Lancer Le Projet

Installer les dépendances :

```bash
poetry install
```

Démarrer PostgreSQL :

```bash
docker compose up -d postgres
```

Lancer l'API :

```bash
poetry run retainflow-api
```

Dans un deuxième terminal, lancer l'interface :

```bash
python -m http.server 5500 --directory app
```

Ouvrir ensuite :

```text
http://127.0.0.1:5500
```

## Commandes Utiles

Construire ou reconstruire les données :

```bash
poetry run retainflow-build-data --reset --n-customers 10000
```

Créer le dashboard de drift :

```bash
poetry run retainflow-drift-dashboard --config config/churn_model.yml
```

Entraîner le modèle :

```bash
poetry run retainflow-train-churn --config config/churn_model.yml
```

Construire la file de rétention :

```bash
poetry run retainflow-build-retention-queue --config config/churn_model.yml
```

Générer les recommandations :

```bash
poetry run retainflow-build-retention-recommendations --config config/churn_model.yml
```

## MLflow

RetainFlow utilise un MLflow local centralisé afin de suivre les expériences, les métriques, les modèles et les artefacts.

La configuration se trouve dans :

```text
config/churn_model.yml
```

## Documentation

Les documents principaux sont :

```text
docs/01_architecture_data_model.md
docs/02_etat_de_l_art_retainflow.md
docs/03_agentic_architecture_retainflow.md
docs/04_fonctionnement_agents_retainflow.md
docs/05_analyse_integration_axa_chat_app.md
```

## État Actuel

Le projet dispose aujourd'hui :

- d'une base PostgreSQL locale ;
- d'un pipeline data science structuré ;
- d'un modèle CatBoost ;
- d'une analyse du drift et du leakage ;
- d'une couche SHAP ;
- d'une logique de priorisation rétention ;
- d'un corpus RAG marketing ;
- d'agents Python ;
- d'une API FastAPI ;
- d'une interface web locale.

RetainFlow est donc une base solide pour construire progressivement un assistant métier de rétention client, capable de combiner données, modèle, explications et recommandations.
