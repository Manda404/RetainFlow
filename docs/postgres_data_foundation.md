# RetainFlow PostgreSQL Data Foundation

Cette brique remplace la creation des tables Databricks pour la premiere etape du projet. PostgreSQL devient la source operationnelle locale: tables relationnelles, contraintes, cles et donnees synthetiques realistes focalisees sur la France.

## Demarrer PostgreSQL

```bash
docker compose up -d postgres
```

Le conteneur expose:

```text
host: localhost
port: 55432
database: retainflow
user: retainflow
password: retainflow
schema: retainflow
```

## Generer Les CSV Puis Alimenter La Base

```bash
poetry run python -m retainflow.pipelines.build_dataset --reset --n-customers 10000
```

Le flux est volontairement decoupe:

```text
generation Python -> fichiers CSV par table -> ETL sequentiel -> PostgreSQL
```

Les CSV sont ecrits ici par defaut:

```text
data/raw/retainflow_csv/
```

Les donnees CSV contiennent aussi des imperfections controlees: valeurs manquantes sur des champs optionnels, satisfactions absentes, agents absents sur certains canaux, dates de fermeture absentes, etc. Ces cas servent ensuite au preprocessing.

Volumes recommandes:

```text
1000      smoke test rapide
10000     developpement local confortable
50000     dataset ML plus serieux
100000+   backtests plus realistes si la machine suit
```

## Splits ML

Les snapshots et labels couvrent 2020 a 2026:

```text
train       observations 2020-01-01 a 2023-12-31
validation 2024-01-01 a 2024-12-31
test        2025-01-01 a 2025-12-31
backtest    2026-01-01 a 2026-06-30
```

## Requetes Utiles

```sql
SELECT split_name, count(*), avg(churn_label)
FROM retainflow.churn_label
GROUP BY split_name
ORDER BY split_name;

SELECT agency_name, region, count(*) AS customers
FROM retainflow.dim_customer c
JOIN retainflow.dim_agency a ON a.agency_id = c.home_agency_id
JOIN retainflow.dim_geography g ON g.geography_id = a.geography_id
GROUP BY agency_name, region
ORDER BY customers DESC
LIMIT 10;
```
