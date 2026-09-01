# Corpus RAG - Strategies Marketing Et Retention

Ce dossier contient le corpus documentaire utilise par `StrategyRAGAgent` et par le workflow de Corrective RAG de RetainFlow.

Chaque document est redige comme une fiche operationnelle pour une equipe retention assurance. Le but n'est pas de stocker du texte generique, mais de fournir au RAG des decisions metier reutilisables dans les reponses agentiques.

## Structure Des Fiches

Chaque fiche contient :

- le segment client cible ;
- les signaux de risque observables dans les tables RetainFlow ;
- le diagnostic metier a confirmer ;
- la strategie recommandee ;
- le canal conseille ;
- un script ou message conseiller ;
- les garde-fous commerciaux, relationnels ou conformite ;
- les KPI de suivi ;
- les mots-cles utiles pour le retrieval.

## Fiches Disponibles

| Document | Cas couvert |
| --- | --- |
| `strategie_sensibilite_prix.md` | Clients sensibles au prix, hausse de prime, devis concurrent. |
| `strategie_insatisfaction_service.md` | Reclamations, SLA degrade, dossier non resolu, faible satisfaction. |
| `strategie_incidents_paiement.md` | Rejets, retards, fragilite budgetaire, regularisation. |
| `strategie_renouvellement_proche.md` | Echeance proche, risque de non-renouvellement, appel proactif. |
| `strategie_reengagement_digital.md` | Faible activite digitale, baisse d'engagement, relance email/mobile. |
| `strategie_sinistre_recent.md` | Sinistre recent, indemnisation sensible, besoin d'accompagnement. |
| `strategie_client_haute_valeur.md` | Client rentable ou multi-contrats avec risque eleve. |

## Utilisation Dans RetainFlow

Le RAG suit une logique corrective :

1. rechercher les documents pertinents avec la question utilisateur ;
2. evaluer si le score de retrieval est suffisant ;
3. enrichir la requete avec des synonymes assurance-retention si les resultats sont faibles ;
4. relancer la recherche ;
5. retourner les documents avec le statut `relevant`, `corrected`, `low_confidence` ou `no_match`.

Cette approche evite de retourner trop vite une strategie peu pertinente et rend les traces de recherche visibles dans les metadonnees de l'agent.
