Oui. Ton idée est beaucoup plus forte qu’un simple projet de **churn prediction**. Le vrai sujet que tu veux traiter est le **passage de la prédiction à l’action métier**.

Le problème que tu as observé est très concret : une entreprise peut avoir un excellent modèle qui identifie des centaines ou des milliers de clients à risque de résiliation, mais si les équipes commerciales ou de rétention ne savent pas **qui contacter en priorité, pourquoi, avec quelle offre, par quel canal et avec quel message**, la valeur du modèle reste limitée.

Je reformulerais donc le projet autour de cette problématique :

> **Comment transformer automatiquement les prédictions d’un modèle de churn en actions de rétention personnalisées, prioritaires et directement exploitables par les équipes métier ?**

Et surtout, je ne l’appellerais plus **AXA Retention Copilot**, parce que le projet dépasse largement le cadre d'un simple copilote.

## Le projet que je te propose

Je l’appellerais :

### **RetainAI — Agentic Customer Retention Platform**

Le nom permet immédiatement de comprendre :
**Retention + AI**, sans être lié à AXA, donc tu peux publier le projet sur GitHub, le présenter en entretien ou l'adapter à une banque, une assurance, un opérateur télécom, etc.

Une autre possibilité très professionnelle serait **Customer Retention Intelligence Platform**, mais **RetainAI** est beaucoup plus mémorable.

---

## La vraie vision du projet

Imagine une compagnie d'assurance fictive disposant de plusieurs centaines de milliers de clients.

Chaque jour, des événements apparaissent :

* expiration prochaine d'un contrat ;
* hausse de prime ;
* sinistre récent ;
* réclamation ;
* retard de paiement ;
* diminution des interactions ;
* changement de situation client ;
* absence de renouvellement ;
* changement de produit ;
* historique d'appels ;
* satisfaction client ;
* etc.

Aujourd'hui, un Data Scientist construirait généralement quelque chose comme :

**Données → Feature Engineering → Modèle → Score de churn**

Par exemple :

> Client A → probabilité de churn = **87 %**

Mais ce n'est pas suffisant.

La vraie question métier est ensuite :

> **Et maintenant, qu'est-ce qu'on fait de cette information ?**

C'est exactement là que ton projet devient intéressant.

Ton architecture deviendrait :

**Données → ML → Priorisation → Raisonnement agentique → Stratégie de rétention → Action → Monitoring**

---

# 1. Une compagnie d'assurance synthétique

On commence effectivement par construire notre propre environnement d'entreprise.

Pas simplement un gros CSV.

Je veux qu'on simule **un véritable système d'information assurance**.

Nous allons créer dans Databricks une architecture de données avec plusieurs tables reliées entre elles.

Par exemple :

```text
                    ┌──────────────────┐
                    │   dim_customer   │
                    └────────┬─────────┘
                             │
                             │
                    ┌────────▼─────────┐
                    │   fact_policy    │
                    └────────┬─────────┘
                             │
          ┌──────────────────┼───────────────────┐
          │                  │                   │
          ▼                  ▼                   ▼
   fact_claims        fact_payments       fact_interactions

          │                                      │
          │                                      ▼
          │                              fact_marketing_events
          │
          ▼
   customer_feedback
```

Je partirais même sur **8 à 10 tables**, plutôt que seulement cinq.

Par exemple :

| Table                      | Rôle                                    |
| -------------------------- | --------------------------------------- |
| `dim_customer`             | identité et profil client               |
| `dim_product`              | produits d'assurance                    |
| `fact_policy`              | contrats détenus                        |
| `fact_claims`              | sinistres                               |
| `fact_payments`            | paiements / impayés                     |
| `fact_interactions`        | appels, emails, agence, application     |
| `fact_marketing_campaigns` | campagnes reçues                        |
| `fact_customer_service`    | demandes / réclamations                 |
| `fact_quotes`              | devis / propositions commerciales       |
| `fact_retention_actions`   | actions réalisées par notre futur agent |

Cela donnera beaucoup plus de richesse au modèle.

---

# 2. Faker ne doit pas seulement générer des données aléatoires

C'est un point extrêmement important.

On utilisera effectivement **Faker**, NumPy et éventuellement d'autres bibliothèques.

Mais il ne faudra surtout pas faire :

```python
churn = random.choice([0, 1])
```

Sinon notre modèle apprendrait essentiellement du bruit.

Nous allons créer une **population avec des comportements cohérents**.

Par exemple, un client ayant :

* plusieurs réclamations ;
* une hausse récente de cotisation ;
* une faible satisfaction ;
* plusieurs appels au service client ;
* un paiement rejeté ;
* une faible ancienneté ;

aura statistiquement beaucoup plus de chances de churner.

Nous pourrons définir quelque chose comme :

```text
P(churn) =
    ancienneté
  + augmentation_tarif
  + nombre_reclamations
  + incidents_paiement
  + satisfaction
  + engagement_digital
  + nombre_sinistres
  + interaction_service_client
  + compétitivité_prix
  + ...
```

avec du bruit statistique pour éviter que le problème soit trivial.

Donc notre dataset synthétique aura une **véritable logique métier sous-jacente**.

C'est ce qui permettra ensuite de construire un vrai projet ML.

---

# 3. Le modèle de churn

Ensuite seulement viendra la partie Data Science.

Nous construirons une table analytique :

```text
customer_360_features
```

obtenue à partir des différentes tables.

Par exemple :

```text
customer_id
age
customer_tenure
total_premium
number_of_policies
claims_12m
claim_amount_12m
payment_incidents_6m
complaints_6m
calls_customer_service_3m
premium_increase_pct
days_since_last_login
email_open_rate
customer_satisfaction
...
```

Puis plusieurs modèles pourront être comparés :

```text
Logistic Regression
Random Forest
LightGBM
XGBoost
CatBoost
```

avec MLflow pour :

* tracking ;
* comparaison des expériences ;
* hyperparameters ;
* metrics ;
* artifacts ;
* model registry.

Et nous ne regarderons pas seulement l'AUC.

Parce que pour ton problème, les métriques les plus intéressantes deviennent :

```text
Precision@K
Recall@K
Lift@K
Gain
Top-decile lift
```

Pourquoi ?

Parce que si le service rétention peut appeler seulement **500 clients par jour**, la question n'est pas :

> Combien de churners mon modèle identifie-t-il globalement ?

Mais :

> Parmi les 500 clients que l'équipe peut contacter aujourd'hui, combien sont réellement des clients à risque ?

C'est exactement le problème que tu décrivais.

---

# 4. On ajoute une notion essentielle : le Business Priority Score

C'est ici que je veux enrichir ton idée.

Un client avec :

```text
P(churn) = 95 %
```

n'est pas forcément le client le plus important.

Imagine :

```text
Client A
P(churn) = 95 %
Valeur annuelle = 180 €
```

et :

```text
Client B
P(churn) = 78 %
Valeur annuelle = 4 500 €
```

Les équipes métier auront probablement intérêt à traiter le client B en priorité.

Nous pouvons donc créer :

### **Retention Priority Score**

quelque chose comme :

```text
Priority Score =
    churn_probability
    × customer_lifetime_value
    × retention_probability
    × business_priority
```

Nous pourrons donc avoir :

```text
Churn Score
Value Score
Retention Propensity
Priority Score
```

C'est beaucoup plus proche d'un véritable système décisionnel.

---

# 5. Ensuite arrive ton Agent

Et c'est ici que le projet change complètement de dimension.

Chaque jour :

```text
Databricks Job
      ↓
Retention Agent
      ↓
sélection des clients
      ↓
Churn Model
      ↓
Priority Engine
      ↓
Customer 360
      ↓
Strategy Engine
      ↓
LLM
      ↓
Recommended Action
```

L'agent pourrait recevoir :

```text
customer_id = CUST_72839
```

et commencer son investigation.

Il récupère :

```text
Profil client

Contrats

Sinistres

Paiements

Interactions

Réclamations

Historique marketing
```

Puis le modèle retourne :

```text
Churn probability = 0.87
```

L'agent analyse ensuite **pourquoi**.

Par exemple :

```text
Main churn drivers

+22% premium increase
3 customer-service complaints
2 payment incidents
no mobile-app connection for 71 days
contract renewal in 18 days
```

---

# 6. Le Strategy Engine

Ton idée d'avoir une base de stratégies marketing est excellente.

Nous pourrons créer quelque chose comme :

```text
retention_strategy_catalog
```

avec :

```text
strategy_id
segment
churn_reason
customer_value
recommended_channel
recommended_offer
discount_limit
message_tone
expected_conversion
```

Exemple :

```text
Reason:
Premium increase

Customer:
High value

Strategy:
Loyalty discount

Offer:
10% premium reduction

Channel:
Phone + Email
```

L'agent pourra consulter cette base avant de décider quoi proposer.

---

# 7. Puis génération automatique d'une recommandation métier

Au final l'équipe métier pourrait recevoir quelque chose comme :

```text
CUSTOMER RETENTION ALERT

Customer
Jean Dupont

Churn Risk
87%

Priority
HIGH

Estimated Annual Value
€2,480

Likely Churn Drivers
• Premium increased by 18%
• 2 complaints in last 90 days
• No digital activity for 42 days

Recommended Action
Call customer within 24h.

Recommended Offer
5–10% loyalty discount.

Alternative
Free assistance option for 12 months.

Preferred Channel
Phone

Agent Suggested Message
...
```

Là, tu ne donnes plus simplement un score à l'équipe métier.

Tu lui donnes **une décision préparée**.

---

# 8. Mais je rajouterais quelque chose d'encore plus important : Human-in-the-loop

Je ne ferais pas envoyer immédiatement tous les emails par l'agent.

Architecture initiale :

```text
Agent
 ↓
propose l'action
 ↓
Business user
 ↓
Approve / Modify / Reject
 ↓
Action
```

Et nous enregistrons :

```text
agent_recommendation
human_decision
action_taken
customer_response
retention_success
```

Cela permettra ensuite à notre système **d'apprendre des actions efficaces**.

---

# 9. Et là apparaît la boucle complète

Notre plateforme devient :

```text
                CUSTOMER DATA
                     │
                     ▼
              CUSTOMER 360
                     │
                     ▼
               CHURN MODEL
                     │
                     ▼
             PRIORITY ENGINE
                     │
                     ▼
              RETENTION AGENT
                │          │
                ▼          ▼
        Customer Context   Strategy DB
                │          │
                └────┬─────┘
                     ▼
               LLM Reasoning
                     │
                     ▼
           Recommended Action
                     │
                     ▼
              Human Approval
                     │
                     ▼
             Customer Contact
                     │
                     ▼
                Outcome
                     │
                     ▼
               Monitoring
                     │
                     └──────────► Model / Strategy
```

Et ça, pour moi, c'est véritablement **RetainAI**.

---

# 10. Internet peut également avoir un rôle

Tu mentionnais vouloir permettre à l'agent de rechercher sur Internet.

Oui, mais je ne donnerais pas Internet à l'agent simplement pour dire qu'il sait chercher.

Il faut une vraie justification métier.

Par exemple :

```text
Competitive Intelligence Agent
```

Il pourrait rechercher des informations publiques sur :

* nouvelles offres concurrentes ;
* tendances tarifaires ;
* changements réglementaires ;
* nouvelles garanties ;
* événements affectant certains produits ;
* tendances du marché de l'assurance.

Ces informations pourraient enrichir le contexte avant de recommander une stratégie.

Cela pourrait devenir une phase plus avancée du projet.

---

# 11. Le projet n'est donc plus seulement Machine Learning

Il réunira plusieurs compétences extrêmement intéressantes :

```text
Data Engineering
    ↓
Databricks / Delta Lake

Analytics Engineering
    ↓
Star Schema / Customer 360

Data Science
    ↓
Churn prediction

MLOps
    ↓
MLflow / Model Registry / Monitoring

Decision Science
    ↓
Prioritization / CLV / Lift

Generative AI
    ↓
LLM reasoning

Agentic AI
    ↓
Tools / orchestration / memory

Marketing
    ↓
Retention strategies

Human-in-the-loop
    ↓
Approval workflow

Monitoring
    ↓
Business + ML + Agent metrics
```

C'est justement ce qui en fait un très bon projet de portfolio pour ton positionnement Data Science / ML Engineering / GenAI.

---

# 12. Je structurerais donc le projet en 6 grandes phases

Une seule feuille de route suffit :

1. **Insurance Data Platform** — génération de plusieurs centaines de milliers de clients, architecture en étoile, Delta Tables, Bronze/Silver/Gold et Customer 360.

2. **Churn Intelligence** — feature engineering, modèle de churn, MLflow, SHAP, calibration, Lift@K et segmentation du risque.

3. **Retention Decision Engine** — Customer Lifetime Value, score de priorité, catalogue de stratégies marketing et Next Best Action.

4. **Retention Agent** — agent Databricks capable d'interroger les tables, appeler le modèle, analyser un client, consulter les stratégies et générer une recommandation.

5. **Activation** — génération d'emails, scripts téléphoniques et tâches pour les équipes métier, avec validation humaine.

6. **Continuous Learning** — monitoring du modèle, efficacité des stratégies, résultats des campagnes, drift et réentraînement.

Le point le plus important est donc celui-ci : **le projet ne cherche pas à prédire le churn. Il cherche à industrialiser la décision de rétention après la prédiction du churn.**

C'est cette formulation qui donne toute sa valeur au projet.
