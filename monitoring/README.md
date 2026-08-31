# RetainFlow - Monitoring

Ce dossier est reserve a la future supervision locale.

La premiere version active doit superviser PostgreSQL, pas Databricks:

```text
volumes par table
qualite referentielle PostgreSQL
distribution des labels churn
drift train / validation / test / backtest
qualite des predictions
qualite des recommandations de retention
```

Pour l'instant, les controles utiles sont des requetes SQL directes sur PostgreSQL.

```sql
SELECT split_name, count(*) AS rows, avg(churn_label) AS churn_rate
FROM retainflow.churn_label
GROUP BY split_name
ORDER BY split_name;
```
