# Strategie Retention - Clients Sensibles Au Prix

## Objectif

Reduire le churn des clients qui percoivent une degradation du rapport prix-valeur apres une hausse de prime, un devis concurrent ou une comparaison tarifaire defavorable.

## Segment Cible

Clients avec forte sensibilite prix, hausse de prime recente, competitor price index faible, demande de devis concurrent, baisse d'engagement ou signaux de contestation tarifaire.

## Signaux A Surveiller

- `premium_increase_pct_max_12m` eleve;
- `competitor_price_index_avg_6m` inferieur a 0.95;
- plusieurs devis concurrents recents;
- `quote_count_6m` ou `competitor_quote_count_6m` en hausse;
- `annual_premium_amount` important par rapport au segment;
- baisse d'engagement email;
- risque de churn moyen a tres eleve;
- interaction recente contenant une objection prix, remise, tarif, mensualisation ou franchise.

## Diagnostic Metier

Le conseiller doit distinguer trois situations :

1. le client veut payer moins cher sans changer ses garanties ;
2. le client ne comprend plus la valeur de ses garanties ;
3. le client a un vrai changement de besoin qui rend le contrat actuel mal ajuste.

La bonne strategie depend de cette qualification. Une remise automatique peut sauver le contrat a court terme mais degrader la marge si le besoin principal est plutot l'ajustement des garanties.

## Action Recommandee

Proposer une revue de contrat orientee valeur :

- expliquer la hausse de prime avec des elements concrets ;
- comparer les garanties maintenues avec les besoins actuels ;
- proposer un ajustement de franchise, de garanties ou de mensualisation ;
- reserver la remise fidelite controlee aux clients rentables ou fortement menaces ;
- documenter la raison de l'offre pour mesurer son efficacite.

## Canal Conseille

- telephone pour les clients `HIGH_VALUE`;
- email personnalise si le client est digital et consentant;
- tache agence si le client prefere le contact local.
- aucun contact commercial agressif si le client vient deja d'exprimer une reclamation ouverte.

## Message Metier

Bonjour,

Nous avons identifie que votre contrat a evolue recemment. Je vous propose de faire un point rapide afin de verifier que vos garanties restent adaptees a votre situation et que le niveau de cotisation correspond bien a vos besoins actuels.

L'objectif est de regarder ensemble les options possibles : ajustement de garanties, franchise, mensualisation ou avantage fidelite si votre situation y est eligible.

## Offre A Privilegier

- remise fidelite plafonnee pour un client rentable et fortement expose ;
- ajustement de franchise si le client accepte un niveau de risque plus eleve ;
- regroupement de contrats si plusieurs produits sont actifs ;
- mensualisation ou changement de date de prelevement si l'objection prix cache une contrainte budgetaire.

## Garde-Fous

- ne pas proposer de remise automatique sans validation;
- verifier l'eligibilite commerciale;
- ne pas promettre un tarif avant simulation;
- prioriser les clients avec valeur annuelle et probabilite de retention suffisantes.
- conserver une trace de la contrepartie proposee.

## KPI De Suivi

- taux d'acceptation de l'offre;
- taux de retention a 90 jours;
- cout moyen de remise;
- valeur sauvee attendue vs valeur sauvee reelle.
- marge preservee apres geste commercial;
- taux de recontact pour motif prix dans les 60 jours.

## Mots-Cles Retrieval

prix, tarif, prime, hausse, augmentation, devis concurrent, competitor price index, remise, fidelite, franchise, mensualisation, rapport prix valeur, objection tarifaire, churn assurance.
