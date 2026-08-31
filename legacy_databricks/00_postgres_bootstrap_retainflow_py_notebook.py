# RetainFlow - PostgreSQL bootstrap notebook

# This notebook is intentionally executable as a normal Python script too:
# poetry run python notebooks/00_postgres_bootstrap_retainflow.py

# %%
from __future__ import annotations

import os
import subprocess
import sys


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
GENERATOR = os.path.join(PROJECT_ROOT, "data_generation", "generate_postgres_data.py")


# %%
N_CUSTOMERS = int(os.getenv("RETAINFLOW_N_CUSTOMERS", "10000"))
SEED = int(os.getenv("RETAINFLOW_SEED", "42"))
DSN = os.getenv(
    "RETAINFLOW_POSTGRES_DSN",
    "postgresql://retainflow:retainflow@localhost:55432/retainflow",
)


# %%
cmd = [
    sys.executable,
    GENERATOR,
    "--reset",
    "--n-customers",
    str(N_CUSTOMERS),
    "--seed",
    str(SEED),
    "--dsn",
    DSN,
]
print(" ".join(cmd))
subprocess.run(cmd, check=True, cwd=PROJECT_ROOT)


# %%
import psycopg

with psycopg.connect(DSN) as conn:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'retainflow'
            ORDER BY table_name
            """
        )
        print("Tables:", [row[0] for row in cur.fetchall()])

        cur.execute(
            """
            SELECT split_name, count(*) AS rows, round(avg(churn_label)::numeric, 4) AS churn_rate
            FROM retainflow.churn_label
            GROUP BY split_name
            ORDER BY split_name
            """
        )
        for row in cur.fetchall():
            print(row)
