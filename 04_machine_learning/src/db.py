"""
db.py
-----
Connexion à l'entrepôt de données PostgreSQL (base `churn_dw`) construit par
le pipeline ETL (`01_etl/`) et documenté dans `02_data_warehouse/`.

Reprend exactement la même convention de configuration que
`01_etl/src/load.py` et `02_data_warehouse/load/load_warehouse.py` : les
paramètres de connexion sont lus depuis des variables d'environnement (à
définir dans un fichier `.env` à la racine du projet, ou dans votre session),
avec des valeurs par défaut pour un PostgreSQL local.

    PGHOST=localhost
    PGPORT=5432
    PGDATABASE=churn_dw
    PGUSER=postgres
    PGPASSWORD=postgres

Dépendances : sqlalchemy, psycopg2-binary.
"""

from __future__ import annotations

import os
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

PG_HOST = os.environ.get("PGHOST", "localhost")
PG_PORT = os.environ.get("PGPORT", "5432")
PG_DATABASE = os.environ.get("PGDATABASE", "churn_dw")
PG_USER = os.environ.get("PGUSER", "postgres")
PG_PASSWORD = os.environ.get("PGPASSWORD", "postgres")


def get_engine() -> Engine:
    """Crée l'engine SQLAlchemy vers l'entrepôt `churn_dw`."""
    url = f"postgresql+psycopg2://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DATABASE}"
    return create_engine(url)


def read_sql(query: str, engine: Engine | None = None, params: dict | None = None) -> pd.DataFrame:
    """Exécute une requête SQL sur l'entrepôt et renvoie un DataFrame pandas."""
    engine = engine or get_engine()
    with engine.connect() as conn:
        return pd.read_sql(text(query), conn, params=params)


def check_connection() -> None:
    """Vérifie que l'entrepôt est accessible et que les tables attendues existent."""
    engine = get_engine()
    expected_tables = {
        "fact_compte_client", "dim_client", "dim_closure_reason",
        "dim_account_category", "dim_industry", "dim_currency", "dim_date",
    }
    with engine.connect() as conn:
        existing = {
            row[0] for row in conn.execute(text(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
            ))
        }
    missing = expected_tables - existing
    if missing:
        raise RuntimeError(
            f"Tables manquantes dans '{PG_DATABASE}' : {missing}. "
            "Avez-vous bien exécuté le pipeline ETL (01_etl/pipeline.py) "
            "et le schéma SQL (02_data_warehouse/schema/create_tables.sql) ?"
        )
    print(f"[db] Connexion OK à '{PG_DATABASE}' sur {PG_HOST}:{PG_PORT} — "
          f"{len(existing)} tables trouvées.")


if __name__ == "__main__":
    check_connection()
