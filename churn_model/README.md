# RetainFlow - Churn Model

Ce dossier documente le chemin ML local. Le code applicatif vit dans `src/retainflow/modeling`.

Source de donnees cible:

```text
retainflow.customer_360_snapshot
retainflow.churn_label
```

Pipeline initial:

```text
1. lire les features et labels depuis PostgreSQL
2. utiliser les splits temporels train / validation / test / backtest
3. entrainer un modele CatBoost
4. logger le run dans MLflow local
5. produire une table de predictions locale
6. associer SHAP au run pour exposer les raisons metier
```

Notebook:

```text
notebooks/01_train_churn_catboost.ipynb
```
