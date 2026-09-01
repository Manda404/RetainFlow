# RetainFlow - Architecture Agentique

## 1. Vision Metier

RetainFlow ne doit pas etre seulement un projet de prediction du churn. Le vrai objectif est de transformer les scores du modele en decisions de retention comprehensibles, priorisees et actionnables par un conseiller, un manager d'agence ou une equipe retention.

Question cible:

```text
Quels sont les 5 prochains clients qu'il faut contacter urgemment, pourquoi,
et quelles actions concretes faut-il proposer ?
```

La reponse attendue ne doit pas etre uniquement une probabilite de churn. Elle doit combiner:

- les donnees client issues de PostgreSQL;
- la prediction du modele CatBoost;
- les facteurs explicatifs SHAP;
- les KPI metier;
- une recommandation de retention;
- un brouillon de message ou de script d'appel;
- une justification claire pour le metier.

## 2. Ce Qui Existe Deja

Le projet dispose deja d'un socle data science solide.

```text
PostgreSQL local
  -> tables relationnelles assurance France
  -> client, agence, contrat, paiement, sinistre, service client, campagne, retention

Dataset analytique
  -> retainflow.customer_360_snapshot
  -> retainflow.churn_label

Modele churn
  -> CatBoostClassifier
  -> split temporel train / validation / test / backtest
  -> MLflow central local
  -> predictions sauvegardees dans retainflow.churn_prediction

Qualite modele
  -> analyse drift
  -> exclusion des features avec drift fort
  -> audit data leakage
  -> matrice de confusion test et backtest
  -> analyse de threshold

Explicabilite
  -> SHAP global
  -> reports/tables/shap_summary.csv
  -> reports/tables/shap_agent_report.json
  -> reports/figures/shap_feature_importance.png

Activation metier
  -> retainflow.retention_priority_queue
  -> retainflow.retention_recommendation
```

La prochaine etape consiste a exposer ces briques sous forme d'outils pilotables par des agents.

## 3. Architecture Cible

```text
Utilisateur metier
      |
      v
Supervisor / Router Agent
      |
      +--> SQL Agent
      |       -> interroge PostgreSQL en lecture seule
      |
      +--> KPI Agent
      |       -> calcule churn rate, volumes, top agences, actions, performance
      |
      +--> Churn Model Agent
      |       -> appelle le modele ou une API de scoring
      |
      +--> Explainability Agent
      |       -> recupere SHAP global et SHAP local par client
      |
      +--> Customer Profile Agent
      |       -> assemble le profil 360 d'un client precis
      |
      +--> Retention Advisor Agent
      |       -> propose la meilleure action de retention
      |
      +--> Data Visualization Agent
      |       -> produit des graphiques Plotly Express, Seaborn ou Matplotlib
      |
      +--> Email Drafting Agent
      |       -> redige email, SMS ou script d'appel
      |
      +--> Strategy RAG Agent
              -> recherche dans les documents internes de strategie
```

Le supervisor ne doit pas faire tout le travail lui-meme. Il analyse la demande, choisit les bons outils, controle les resultats, puis compose une reponse finale claire.

## 4. Agents A Creer

### SupervisorAgent

Role:

- comprendre la demande utilisateur;
- decomposer la demande en etapes;
- choisir les agents et outils necessaires;
- verifier que les resultats sont coherents;
- produire la reponse finale.

Exemple:

```text
Demande: "Donne-moi les 5 clients a contacter en urgence."

Plan:
1. Interroger la priority queue.
2. Recuperer les predictions du dernier run MLflow.
3. Recuperer les explications SHAP locales.
4. Generer une recommandation metier.
5. Produire un message conseiller.
```

### SQLAgent

Role:

- traduire une question metier en SQL;
- utiliser uniquement des requetes `SELECT`;
- s'appuyer sur le schema PostgreSQL;
- refuser les requetes dangereuses ou trop larges;
- retourner un resultat structure.

Tables prioritaires:

```text
retainflow.dim_customer
retainflow.dim_agency
retainflow.customer_360_snapshot
retainflow.churn_label
retainflow.churn_prediction
retainflow.retention_priority_queue
retainflow.retention_recommendation
```

Exemples de questions:

```text
Quels sont les clients CRITICAL de la region Ile-de-France ?
Quels clients ont une forte probabilite de churn et une forte valeur annuelle ?
Quelles agences concentrent le plus de clients a risque ?
```

### KPIAgent

Role:

- calculer des indicateurs decisionnels;
- produire des tables synthetiques pour le supervisor;
- expliquer les tendances.

KPI utiles:

```text
churn_rate par split
volume de clients a risque par region
volume par priority_tier
taux de churn predit par agence
valeur sauvee attendue
repartition des actions recommandees
precision, recall, lift et confusion matrix du modele
```

### CustomerProfileAgent

Role:

- recuperer le profil complet d'un client;
- joindre identite, agence, region, snapshot analytique, prediction, priorite et recommandation;
- fournir le contexte necessaire avant une explication SHAP, une action retention ou un email.

Cet agent remplace l'ancien `ChurnModelAgent` dans la couche active. C'est plus utile pour le metier, car une prediction seule ne suffit pas a prendre une decision.

Le chargement du modele depuis MLflow reste necessaire, mais il doit etre implemente comme `ModelTool` ou API `/predict/churn`, pas comme agent autonome au debut.

### ExplainabilityAgent

Role:

- expliquer pourquoi le modele predit un risque de churn;
- utiliser les artefacts SHAP globaux;
- ajouter une explication locale par client;
- transformer les features techniques en raisons metier.

Artefacts actuels:

```text
reports/tables/shap_summary.csv
reports/tables/shap_agent_report.json
reports/figures/shap_feature_importance.png
```

Evolution necessaire:

```text
retainflow.churn_prediction_explanation
  observation_date
  customer_id
  split_name
  feature
  feature_value
  shap_value
  impact_direction
  business_description
  mlflow_run_id
```

Cette table permettra a l'agent de dire:

```text
Le risque augmente surtout a cause des incidents de paiement,
de la hausse de prime recente et d'une faible satisfaction service.
```

### RetentionAdvisorAgent

Role:

- transformer les scores en action;
- expliquer pourquoi un client est prioritaire;
- proposer une offre ou une action;
- tenir compte du canal autorise et du consentement client.

Il s'appuie sur:

```text
retainflow.retention_priority_queue
retainflow.retention_recommendation
reports/tables/retention_priority_queue.csv
reports/tables/retention_recommendation.csv
```

### DataVisualizationAgent

Role:

- comprendre quand l'utilisateur demande un visuel;
- transformer un resultat SQL ou un resultat modele en `pandas.DataFrame`;
- choisir le graphique adapte;
- produire le code Python et/ou la figure;
- privilegier Plotly Express pour les graphiques interactifs;
- utiliser Seaborn ou Matplotlib lorsque le besoin est plus statistique ou plus controle.

Bibliotheques prioritaires:

```text
plotly.express as px
seaborn as sns
matplotlib.pyplot as plt
pandas as pd
```

Types de graphiques a supporter:

```text
bar plot
line chart temporel
histogramme
box plot
scatter plot
heatmap
pie chart uniquement si le nombre de categories est tres faible
table analytique triee
```

Exemples de questions:

```text
Montre-moi le taux de clients contactes cette semaine par agence.
Fais un bar plot des clients a risque par region.
Visualise la repartition des actions recommandees.
Montre l'evolution du churn rate par date d'observation.
Affiche les 10 clients les plus urgents avec leur probabilite de churn.
Compare les predictions test et backtest.
```

Flux attendu:

```text
1. SupervisorAgent detecte une demande avec visualisation.
2. SQLAgent construit une requete SELECT controlee.
3. SQLTool execute la requete et retourne un DataFrame.
4. DataVisualizationAgent inspecte les colonnes et choisit un graphique.
5. VisualizationTool genere la figure Plotly Express.
6. SupervisorAgent retourne le graphique, le commentaire et la requete source.
```

Exemple pour "taux de clients contactes cette semaine par agence":

```sql
SELECT
  a.agency_name,
  count(*) AS clients_contactes,
  avg(CASE WHEN r.human_review_status = 'APPROVED' THEN 1 ELSE 0 END) AS taux_actions_validees
FROM retainflow.retention_recommendation r
JOIN retainflow.dim_customer c
  ON c.customer_id = r.customer_id
JOIN retainflow.dim_agency a
  ON a.agency_id = c.home_agency_id
WHERE r.created_at >= date_trunc('week', current_date)
GROUP BY a.agency_name
ORDER BY clients_contactes DESC
LIMIT 20;
```

Exemple de visualisation prioritaire avec Plotly Express:

```python
import plotly.express as px

fig = px.bar(
    df,
    x="agency_name",
    y="clients_contactes",
    color="taux_actions_validees",
    title="Clients contactes cette semaine par agence",
    labels={
        "agency_name": "Agence",
        "clients_contactes": "Clients contactes",
        "taux_actions_validees": "Taux actions validees",
    },
)
fig.update_layout(xaxis_tickangle=-35)
fig.show()
```

Le graphique doit toujours etre accompagne:

- de la requete SQL source;
- du nombre de lignes utilisees;
- d'une interpretation courte;
- d'un avertissement si les donnees sont incompletes ou filtrees;
- du chemin du fichier si le graphique est sauvegarde.

### EmailDraftingAgent

Role:

- rediger un email, un SMS ou un script d'appel;
- adapter le ton au segment client;
- integrer la raison de contact;
- ne jamais envoyer automatiquement sans validation humaine.

Exemple de sortie:

```text
Objet: Faisons le point sur votre contrat habitation

Bonjour Madame Martin,
Nous souhaitons faire un point avec vous afin de verifier que votre contrat
reste bien adapte a votre situation actuelle...
```

### StrategyRAGAgent

Role:

- rechercher dans les documents internes;
- retrouver les politiques commerciales, scripts, offres, contraintes legales;
- enrichir les recommandations avec une source documentaire.

Sources futures:

```text
data/docs/strategy_marketing/
docs/strategy/
docs/compliance/
docs/product_catalog/
```

Le RAG ne remplace pas le modele. Il apporte du contexte metier et de la strategie.

### Data Quality Comme Garde-Fou Interne

Les controles drift et leakage restent importants, mais ils ne sont pas gardes comme agent autonome dans la version active.

Role futur:

- exposer les rapports de drift;
- exposer l'audit leakage;
- alerter le supervisor si le modele est fragile;
- expliquer pourquoi certaines variables ont ete retirees.

Sources:

```text
reports/tables/churn_drift_report.csv
reports/tables/churn_drift_summary.json
reports/tables/drift_feature_exclusions.json
reports/tables/data_leakage_report.csv
```

## 5. Outils Techniques A Exposer

Les agents doivent appeler des outils simples, testes et reutilisables.

```text
src/retainflow/tools/sql_tool.py
  -> execute du SQL read-only sur PostgreSQL

src/retainflow/tools/kpi_tool.py
  -> retourne les KPI retention et modele

src/retainflow/tools/model_tool.py
  -> score des clients avec le modele CatBoost

src/retainflow/tools/customer_profile_tool.py
  -> recupere le profil client 360, prediction et recommandation

src/retainflow/tools/explainability_tool.py
  -> retourne SHAP global et local

src/retainflow/tools/retention_tool.py
  -> lit priority queue et recommendations

src/retainflow/tools/visualization_tool.py
  -> genere des figures Plotly Express, Seaborn ou Matplotlib

src/retainflow/tools/email_tool.py
  -> genere un brouillon d'email ou script d'appel

src/retainflow/tools/rag_tool.py
  -> recherche documentaire strategie
```

## 6. Variables D'Environnement

Les secrets et endpoints ne doivent pas etre hardcodes dans les notebooks.

Fichier cible:

```text
.env
```

Exemple a fournir dans `.env.example`:

```bash
RETAINFLOW_POSTGRES_DSN=postgresql://retainflow:retainflow@localhost:55432/retainflow
MLFLOW_TRACKING_URI=sqlite:////Users/surelmanda/.mlflow/mlflow.db
MLFLOW_ARTIFACT_URI=file:///Users/surelmanda/.mlflow/artifacts

RETAINFLOW_MODEL_NAME=retainflow_churn_catboost
RETAINFLOW_MODEL_API_URL=http://127.0.0.1:8000
RETAINFLOW_AGENT_LOG_LEVEL=INFO
RETAINFLOW_RAG_DOCS_DIR=data/docs/strategy_marketing

LLM_PROVIDER=openai
LLM_MODEL=gpt-4.1-mini
OPENAI_API_KEY=
```

Les cles API seront ajoutees plus tard par l'utilisateur. Le projet doit fonctionner en mode local autant que possible tant que les cles ne sont pas disponibles.

## 7. API A Prevoir

Une API locale permettra de separer le modele et les agents.

```text
src/retainflow/api/
  app.py
  schemas.py
  model_service.py
```

Endpoints proposes:

```text
GET  /health
POST /predict/churn
POST /explain/churn
GET  /kpi/retention
GET  /clients/priority
POST /recommend/action
POST /visualize
POST /draft/email
```

Contrat minimal pour `/predict/churn`:

```json
{
  "customer_ids": ["CUST_000001", "CUST_000042"],
  "observation_date": "2026-06-30",
  "include_explanations": true
}
```

Reponse attendue:

```json
{
  "model_name": "retainflow_churn_catboost",
  "mlflow_run_id": "...",
  "predictions": [
    {
      "customer_id": "CUST_000001",
      "churn_probability": 0.72,
      "risk_band": "VERY_HIGH",
      "top_drivers": [
        {
          "feature": "payment_incidents_6m",
          "feature_value": 2,
          "shap_value": 0.41,
          "business_description": "Incidents de paiement recents"
        }
      ]
    }
  ]
}
```

## 8. Structure De Projet Cible

```text
src/retainflow/
  agents/
    supervisor.py
    sql_agent.py
    kpi_agent.py
    customer_profile_agent.py
    explainability_agent.py
    retention_advisor_agent.py
    data_visualization_agent.py
    email_drafting_agent.py
    strategy_rag_agent.py

  tools/
    sql_tool.py
    kpi_tool.py
    model_tool.py
    customer_profile_tool.py
    explainability_tool.py
    retention_tool.py
    visualization_tool.py
    email_tool.py
    rag_tool.py

  api/
    app.py
    schemas.py
    model_service.py

  rag/
    document_loader.py
    vector_store.py
    retriever.py

  prompts/
    supervisor.md
    sql_agent.md
    advisor_agent.md
    visualization_agent.md
    email_agent.md
    rag_agent.md

config/
  agents.yml

notebooks/
  05_agentic_retention_workflow.ipynb
```

Les notebooks doivent rester des notebooks d'execution pedagogique. Toute la logique reutilisable doit vivre dans `src/retainflow`.

## 9. Scenario Bout En Bout

Demande utilisateur:

```text
Quels sont les 5 clients que je dois contacter en urgence cette semaine,
et que dois-je leur proposer ?
```

Execution cible:

```text
1. SupervisorAgent comprend que la demande concerne priorisation + recommandation.
2. SQLAgent lit retainflow.retention_priority_queue.
3. RetentionAdvisorAgent enrichit avec retainflow.retention_recommendation.
4. ExplainabilityAgent recupere les principales raisons SHAP.
5. StrategyRAGAgent verifie les regles de retention applicables.
6. EmailDraftingAgent prepare un message ou un script d'appel.
7. SupervisorAgent retourne une reponse ordonnee.
```

Si l'utilisateur demande un visuel:

```text
1. SupervisorAgent detecte l'intention visualisation.
2. SQLAgent produit la requete.
3. SQLTool retourne un DataFrame.
4. DataVisualizationAgent genere une figure Plotly Express.
5. SupervisorAgent explique le graphique et affiche la figure.
```

Sortie attendue:

```text
1. Client: Jean Martin
   Probabilite de churn: 78 %
   Priorite: CRITICAL
   Pourquoi: hausse de prime, incident paiement, faible satisfaction
   Action conseillee: appel retention + remise fidelite controlee
   Canal: PHONE
   Message conseiller: ...
   Source: model run ..., table retention_priority_queue, SHAP top drivers
```

## 10. Garde-Fous

Les agents doivent etre utiles, mais controles.

```text
SQL
  -> SELECT uniquement
  -> limite de lignes obligatoire
  -> pas de modification de donnees par agent

PII
  -> eviter d'envoyer des donnees personnelles inutiles au LLM
  -> masquer email, telephone, adresse si non necessaire

Modele
  -> toujours retourner model_name et mlflow_run_id
  -> ne pas presenter la prediction comme une certitude
  -> expliquer les limites si drift ou leakage warning

Email
  -> generation de brouillon uniquement
  -> validation humaine obligatoire avant envoi

Decision
  -> l'agent recommande, le metier decide
```

## 11. Ordre D'Implementation

### Phase 1 - Cadrage et configuration

- creer ce document d'architecture;
- creer `.env.example`;
- creer `config/agents.yml`;
- definir les contrats de reponse des outils.

### Phase 2 - Outils read-only

- `SQLTool`;
- `KPITool`;
- `RetentionTool`;
- tests unitaires sur les requetes autorisees et interdites.

### Phase 3 - Modele et explicabilite

- `ModelTool`;
- `ExplainabilityTool`;
- table `churn_prediction_explanation`;
- calcul SHAP local par client;
- API `/predict/churn` et `/explain/churn`.

### Phase 4 - RAG strategie

- ingestion documents strategie;
- recherche documentaire;
- citation des sources internes;
- outil `RAGTool`.

### Phase 5 - Agents

- `SQLAgent`;
- `KPIAgent`;
- `CustomerProfileAgent`;
- `ExplainabilityAgent`;
- `RetentionAdvisorAgent`;
- `DataVisualizationAgent`;
- `EmailDraftingAgent`;
- `StrategyRAGAgent`;
- `SupervisorAgent`.

### Phase 6 - Notebook d'orchestration

- creer `notebooks/05_agentic_retention_workflow.ipynb`;
- executer chaque agent et outil etape par etape;
- montrer une demande metier complete;
- montrer une demande metier avec graphique Plotly Express;
- afficher la reponse finale du supervisor.

## 12. Definition Of Done

La premiere version agentique sera consideree prete lorsque:

- une question metier peut retourner les 5 clients prioritaires;
- chaque client contient score, prediction, recommandation, canal, action, justification;
- les explications SHAP sont disponibles au niveau global et local;
- les requetes SQL sont controlees et read-only;
- les demandes de visualisation retournent un graphique et son interpretation;
- les brouillons d'email ne sont jamais envoyes automatiquement;
- l'API modele fonctionne localement;
- les variables sensibles sont dans `.env`;
- le notebook `05_agentic_retention_workflow.ipynb` montre le workflow complet.
