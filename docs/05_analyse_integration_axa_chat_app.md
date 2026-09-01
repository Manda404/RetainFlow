# Analyse D'Integration - AXA Retention Chat App V2 Vers RetainFlow

## 1. Objectif

Le projet source analyse est:

```text
/Users/surelmanda/2-LLops-Databricks-Projects/AXA-Retention-Agent/axa_retention_chat_app_v2
```

L'objectif n'est pas de copier ce projet dans RetainFlow. L'objectif est d'identifier ce qui est utile, ce qui est trop simplifie, puis de l'adapter intelligemment a l'architecture RetainFlow.

Projet cible:

```text
/Users/surelmanda/2-LLops-Databricks-Projects/RetainFlow
```

## 2. Resume Du Projet AXA

Le projet AXA est une application de demonstration locale.

Structure:

```text
axa_retention_chat_app_v2/
  backend/
    app/
      main.py
      agent_service.py
      schemas.py
    data/
      customer_360_sample.csv
    rag/
      documents/
        commercial_offers.md
        compliance_rules.md
        retention_policy.md
    requirements.txt

  frontend/
    index.html
    app.js
    style.css

  Makefile
  start_app.sh
```

Ce projet contient:

- une API FastAPI simple;
- un endpoint `/health`;
- un endpoint `/chat`;
- un frontend HTML/CSS/JS;
- une animation du parcours SQL -> ML -> RAG -> recommandation;
- un panneau de score churn;
- des cartes de questions rapides;
- un CSV local de clients;
- des regles RAG tres simples;
- un scoring churn simule en Python.

## 3. Ce Qui Est Interessant A Recuperer

### Experience Utilisateur

La partie la plus interessante est l'experience produit:

- interface conversationnelle;
- questions rapides cliquables;
- timeline d'execution des outils;
- panneau de score;
- facteurs de risque visibles;
- recommandation visible;
- statut de connexion API;
- separation backend / frontend.

Cette experience est utile pour RetainFlow car elle montre bien la valeur metier d'un agent:

```text
Question conseiller -> analyse client -> risque -> raisons -> strategie -> action.
```

### API FastAPI

L'idee d'une API locale est pertinente:

```text
GET /health
POST /chat
```

Pour RetainFlow, cette API doit etre enrichie:

```text
GET  /health
POST /chat
GET  /clients/priority
GET  /customers/{customer_id}/profile
POST /sql/query
POST /visualize
POST /rag/search
POST /email/draft
```

### Schema De Reponse

Le projet AXA retourne une reponse structuree:

```text
title
summary
customer_id
churn_score
risk_level
profile
risk_factors
rag_rules
recommendation
```

Cette idee est bonne. Dans RetainFlow, elle doit etre adaptee vers:

```text
answer
data
metadata
sql
mlflow_run_id
shap_drivers
rag_sources
recommendation
visualization
human_review_required
```

Cela correspond deja a notre objet `AgentResponse`.

## 4. Ce Qu'il Ne Faut Pas Copier

### Ne Pas Copier Le Scoring Simule

Dans AXA:

```python
compute_churn_score(row)
```

Le score est calcule avec des regles manuelles:

```text
hausse prime -> +0.25
reclamation -> +0.20
delai sinistre -> +0.20
sentiment negatif -> +0.15
client recent -> +0.10
mono-contrat -> +0.10
```

Ce n'est pas adapte a RetainFlow.

Pourquoi:

- RetainFlow a deja un modele CatBoost;
- les predictions sont sauvegardees dans PostgreSQL;
- le run MLflow est trace;
- les artefacts SHAP existent;
- le scoring manuel casserait la logique data science du projet.

Decision:

```text
Ne pas reprendre compute_churn_score.
Utiliser retainflow.churn_prediction et le futur ModelTool/API.
```

### Ne Pas Copier Le CSV Client

Dans AXA:

```text
backend/data/customer_360_sample.csv
```

Ce CSV sert seulement a une demonstration.

Dans RetainFlow, la source de verite est:

```text
PostgreSQL
retainflow.dim_customer
retainflow.customer_360_snapshot
retainflow.churn_prediction
retainflow.retention_priority_queue
retainflow.retention_recommendation
```

Decision:

```text
Ne pas importer customer_360_sample.csv.
Utiliser CustomerProfileTool + SQLTool.
```

### Ne Pas Copier Les Regles RAG Telles Quelles

Les documents AXA sont utiles mais trop courts:

```text
commercial_offers.md
compliance_rules.md
retention_policy.md
```

Exemple:

```text
Remise fidelite 10%.
Rendez-vous conseiller prioritaire.
Pack Auto + Habitation.
```

Dans RetainFlow, on a deja un corpus plus riche:

```text
data/docs/strategy_marketing/
```

Decision:

```text
Ne pas copier brutalement les fichiers AXA.
Transformer les idees AXA en documents metier RetainFlow plus complets.
```

## 5. Mapping AXA Vers RetainFlow

| AXA Chat App V2 | RetainFlow cible | Decision |
|---|---|---|
| `backend/app/main.py` | `src/retainflow/api/app.py` | Adapter |
| `backend/app/schemas.py` | `src/retainflow/api/schemas.py` | Adapter |
| `backend/app/agent_service.py` | `src/retainflow/agents/supervisor.py` + tools | Ne pas copier |
| `compute_churn_score` | `churn_prediction` + futur `ModelTool` | Supprimer |
| `customer_360_sample.csv` | PostgreSQL RetainFlow | Supprimer |
| `backend/rag/documents` | `data/docs/strategy_marketing` | Enrichir |
| `frontend/index.html` | future app RetainFlow | Adapter visuellement |
| `frontend/app.js` | future app RetainFlow | Adapter contrats API |
| `frontend/style.css` | future app RetainFlow | Refaire style RetainFlow |
| timeline SQL/ML/RAG/Reco | timeline agents/tools | Recuperer l'idee |
| risk ring | churn probability panel | Recuperer l'idee |
| quick question cards | question templates metier | Recuperer l'idee |

## 6. Architecture D'Integration Proposee

```text
RetainFlow
  src/retainflow/
    agents/
      supervisor.py
      sql_agent.py
      kpi_agent.py
      customer_profile_agent.py
      retention_advisor_agent.py
      explainability_agent.py
      data_visualization_agent.py
      email_drafting_agent.py
      strategy_rag_agent.py

    tools/
      sql_tool.py
      kpi_tool.py
      customer_profile_tool.py
      retention_tool.py
      explainability_tool.py
      visualization_tool.py
      email_tool.py
      rag_tool.py

    api/
      app.py
      schemas.py
      chat_service.py

  app/
    index.html
    app.js
    style.css
```

Le dossier `src/retainflow/api` doit exposer les agents existants.

Le dossier `app` doit contenir le frontend RetainFlow. Il ne doit pas etre une copie AXA, mais une interface adaptee a:

- RetainFlow;
- PostgreSQL local;
- agents RetainFlow;
- SHAP;
- RAG marketing;
- visualisations Plotly;
- recommandations a validation humaine.

## 7. Contrat API RetainFlow Propose

### `POST /chat`

Requete:

```json
{
  "message": "Quels sont les 5 clients a contacter en urgence et pourquoi ?",
  "limit": 5
}
```

Reponse:

```json
{
  "agent_name": "SupervisorAgent",
  "answer": "...",
  "response_type": "table",
  "data": [],
  "metadata": {
    "steps": ["RetentionAdvisorAgent", "ExplainabilityAgent"],
    "sql": "...",
    "shap_artifact": "reports/tables/shap_summary.csv"
  }
}
```

### `GET /customers/{customer_id}/profile`

Reponse:

```json
{
  "customer_id": "CUST_000123",
  "profile": {},
  "prediction": {},
  "recommendation": {},
  "metadata": {
    "mlflow_run_id": "...",
    "sql": "..."
  }
}
```

### `POST /rag/search`

Requete:

```json
{
  "query": "strategie marketing pour client sensible au prix",
  "top_k": 5
}
```

Reponse:

```json
{
  "documents": [
    {
      "title": "Strategie Retention - Clients Sensibles Au Prix",
      "path": "data/docs/strategy_marketing/strategie_sensibilite_prix.md",
      "score": 0.42,
      "preview": "..."
    }
  ]
}
```

### `POST /visualize`

Requete:

```json
{
  "message": "Visualise les clients prioritaires par region"
}
```

Reponse:

```json
{
  "response_type": "plotly",
  "figure": {},
  "interpretation": "...",
  "metadata": {
    "sql": "...",
    "chart_type": "bar"
  }
}
```

## 8. UX A Reprendre Mais A Adapter

### Timeline

Dans AXA:

```text
SQL Tool -> ML Scoring -> RAG Rules -> Recommendation
```

Dans RetainFlow:

```text
Supervisor -> SQL/Profile -> Prediction -> SHAP -> RAG Strategy -> Recommendation -> Email/Visual
```

La timeline doit etre dynamique selon la question.

Exemples:

```text
Question KPI + graphique:
SQLAgent -> SQLTool -> DataVisualizationAgent -> Plotly

Question client:
CustomerProfileAgent -> ExplainabilityAgent -> StrategyRAGAgent -> RetentionAdvisorAgent

Question email:
RetentionAdvisorAgent -> StrategyRAGAgent -> EmailDraftingAgent
```

### Panneau De Score

Le risk ring AXA est une bonne idee. Dans RetainFlow, il doit afficher:

- `churn_probability`;
- `churn_risk_band`;
- `priority_score`;
- `priority_tier`;
- `expected_saved_value`;
- `mlflow_run_id`.

### Facteurs De Risque

Dans AXA, les facteurs viennent de regles manuelles.

Dans RetainFlow, ils doivent venir de:

- `action_reason`;
- `business_context`;
- SHAP global maintenant;
- SHAP local ensuite.

### RAG Rules

Dans AXA, les regles sont affichees telles quelles.

Dans RetainFlow, il faut afficher:

- titre du document;
- score de similarite;
- extrait court;
- chemin de source;
- strategie recommandee.

## 9. Plan D'Implementation

### Phase 1 - Backend API RetainFlow

Creer:

```text
src/retainflow/api/
  __init__.py
  app.py
  schemas.py
  chat_service.py
```

Ajouter:

```text
fastapi
uvicorn
```

Endpoints:

```text
GET /health
POST /chat
POST /rag/search
GET /customers/{customer_id}/profile
```

### Phase 2 - Frontend RetainFlow

Creer:

```text
app/
  index.html
  app.js
  style.css
```

Reprendre l'idee AXA, mais changer:

- branding;
- textes;
- parcours agents;
- structure de reponse;
- cartes rapides;
- panneau client;
- RAG sources;
- visualisation Plotly.

### Phase 3 - Integration Des Visualisations

Ajouter un support Plotly dans le frontend:

- si `response_type = "plotly"`, afficher la figure;
- si `response_type = "table"`, afficher une table;
- si `response_type = "email_draft"`, afficher le brouillon.

### Phase 4 - RAG Marketing Enrichi

Completer `data/docs/strategy_marketing` avec:

```text
offres_commerciales.md
regles_conformite.md
politique_retention.md
```

Mais en version RetainFlow enrichie, pas en copie brute du projet AXA.

## 10. Decision Finale

Ce qu'on garde:

- API FastAPI locale;
- frontend chat;
- timeline d'outils;
- risk panel;
- quick actions;
- affichage des facteurs;
- affichage des sources RAG;
- endpoint `/chat`.

Ce qu'on ne garde pas:

- score churn manuel;
- CSV client local;
- logique agent monolithique dans `agent_service.py`;
- branding AXA;
- documents RAG trop courts sans contexte;
- dependances separees `backend/requirements.txt`.

Ce qu'on construit a la place:

```text
Frontend inspire du projet AXA
+ API RetainFlow
+ agents RetainFlow
+ PostgreSQL
+ MLflow
+ SHAP
+ RAG marketing cible
+ visualisations Plotly
```

La bonne integration est donc une adaptation produit et technique, pas une copie.
