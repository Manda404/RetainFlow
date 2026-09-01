# Strategie Retention - Incidents De Paiement

## Objectif

Eviter une rupture de relation lorsque le risque de churn est lie a des contraintes de paiement, des rejets de prelevement, des retards ou une fragilite budgetaire.

## Segment Cible

Clients avec retards, rejets de paiement, impayes, regularisations recentes, revenu estime faible ou moyen, ou demande d'amenagement de paiement.

## Signaux A Surveiller

- `payment_incidents_6m` superieur a 0;
- `late_payment_count_12m` eleve;
- `rejected_payment_count_12m` eleve;
- revenu estime faible ou moyen;
- risque de churn associe a la contrainte budgetaire.
- hausse de prime combinee a un incident de paiement;
- changement recent de coordonnees bancaires;
- faible reste a vivre estime ou segment budget sensible;
- interaction contenant mensualisation, rejet, regularisation, prelevement ou report.

## Diagnostic Metier

Le conseiller doit qualifier si l'incident est ponctuel ou structurel :

- incident ponctuel : probleme technique, changement bancaire, oubli ;
- tension budgetaire : cotisation trop elevee, date de prelevement inadaptee ;
- risque de rupture : client evite le contact, plusieurs rejets, menace de resiliation.

La strategie doit rester accompagnante et conforme. Le ton punitif augmente le risque de churn.

## Action Recommandee

Proposer un amenagement de paiement selon eligibilite :

- changement de date de prelevement ;
- passage a la mensualisation ;
- plan de regularisation court ;
- rappel preventif avant prochaine echeance ;
- revue de garanties si le budget est durablement contraint.

## Canal Conseille

Telephone ou agence pour traiter la situation avec tact. SMS seulement pour rappel simple si consentement explicite.

## Message Metier

Bonjour,

Je vous contacte pour faire le point sur votre mode de paiement et verifier avec vous si l'organisation actuelle reste adaptee. L'objectif est de trouver une solution simple pour eviter de nouveaux incidents et maintenir vos garanties dans de bonnes conditions.

Nous pouvons regarder ensemble la date de prelevement, la mensualisation ou une regularisation adaptee si votre situation le permet.

## Garde-Fous

- respecter les contraintes reglementaires;
- ne pas pousser une offre commerciale inappropriee;
- verifier le consentement canal;
- documenter l'accord client.
- ne jamais promettre l'absence de consequence sans validation des regles internes;
- ne pas exposer la situation financiere du client dans un message non securise.

## KPI De Suivi

- taux de regularisation;
- reduction des rejets;
- retention a 90 jours;
- taux de satisfaction post-contact.
- taux de nouvel incident a 60 jours;
- montant regularise;
- nombre d'echeanciers respectes.

## Mots-Cles Retrieval

paiement, incident, rejet, impaye, retard, prelevement, mensualisation, regularisation, budget, fragilite financiere, date de paiement, retention assurance.
