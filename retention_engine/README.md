# RetainFlow - Retention Engine

Ce dossier est reserve a la prochaine brique decisionnelle.

Le moteur de retention devra consommer les scores churn produits depuis PostgreSQL, puis generer une file de priorite metier:

```text
customer_id
churn_probability
priority_score
priority_tier
recommended_action_type
action_reason
recommended_channel
estimated_offer_value
explainability_summary
```

La prochaine implementation ne doit plus lire des tables Databricks. Elle devra partir de `retainflow.customer_360_snapshot`, `retainflow.churn_label`, puis d'une table locale de predictions a creer.
