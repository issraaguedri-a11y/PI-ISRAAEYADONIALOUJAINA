"""
load.py
-------
Étape LOAD du pipeline ETL du Projet Intégré (Churn Client).

Responsabilités :
- Prendre le fait transformé (transform.py) et le déposer dans un entrepôt
  analytique PostgreSQL, selon un modèle en étoile simplifié : une table de
  faits + des tables de dimensions.
- Créer la base de données cible si elle n'existe pas encore.
- Exporter également une copie Parquet du fait (utile pour le notebook EDA
  et pour l'entraînement du modèle ML sans redépendre du CSV brut, ni de la
  base pour ces usages locaux).

Connexion à PostgreSQL
-----------------------
Les paramètres de connexion sont lus depuis des variables d'environnement
(à définir dans un fichier `.env` à la racine du projet, ou dans votre
session), avec des valeurs par défaut pour un PostgreSQL local :

    PGHOST=localhost
    PGPORT=5432
    PGDATABASE=churn_dw
    PGUSER=postgres
    PGPASSWORD=postgres

Dépendances nécessaires : sqlalchemy, psycopg2-binary (voir requirements.txt).

Exécution directe (construit l'entrepôt complet) :
    python load.py
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import psycopg2
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from transform import transform_all, build_dim_date

BASE_DIR = Path(__file__).resolve().parents[2]

PROCESSED_DIR = BASE_DIR / "01_etl" / "output"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
FACT_PARQUET_PATH = PROCESSED_DIR / "fact_compte_client.parquet"

# ------------------------------------------------------------------
# Configuration PostgreSQL (variables d'environnement, avec valeurs par défaut)
# ------------------------------------------------------------------
PG_HOST = os.environ.get("PGHOST", "localhost")
PG_PORT = os.environ.get("PGPORT", "5432")
PG_DATABASE = os.environ.get("PGDATABASE", "churn_dw")
PG_USER = os.environ.get("PGUSER", "postgres")
PG_PASSWORD = os.environ.get("PGPASSWORD", "postgres")


def _ensure_database_exists() -> None:
    """
    Se connecte à la base 'postgres' (toujours présente) pour créer la base
    cible PG_DATABASE si elle n'existe pas encore. PostgreSQL ne permet pas
    de créer une base depuis une transaction : on passe donc en autocommit.
    """
    conn = psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname="postgres",
        user=PG_USER, password=PG_PASSWORD,
    )
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (PG_DATABASE,))
            if cur.fetchone() is None:
                cur.execute(f'CREATE DATABASE "{PG_DATABASE}"')
                print(f"[load] Base PostgreSQL '{PG_DATABASE}' créée.")
            else:
                print(f"[load] Base PostgreSQL '{PG_DATABASE}' déjà existante.")
    finally:
        conn.close()


def get_engine() -> Engine:
    """Crée l'engine SQLAlchemy vers la base cible (après l'avoir créée si besoin)."""
    _ensure_database_exists()
    url = f"postgresql+psycopg2://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DATABASE}"
    return create_engine(url)

# Colonnes du fait qui vont dans FACT_COMPTE_CLIENT (le reste part dans les
# tables de dimensions dénormalisées pour garder un schéma en étoile lisible).
# Les codes métier (ACCOUNT_CATEGORY, CURRENCY, CLOSURE_REASON, INDUSTRY,
# dates) sont conservés pour la traçabilité/lisibilité ; les surrogate keys
# correspondantes (suffixe _SK) sont ajoutées séparément dans
# build_star_schema_tables pour les usages ML (clés entières, jointures
# stables même si un code métier venait à changer côté source).
FACT_COLUMNS = [
    "CUSTOMER_NO", "ACCOUNT_NO", "BRANCH",
    "ACCOUNT_STATUS", "CHURN", "CLIENT_FULL_CHURN",
    "ACCT_BALANCE", "SALARY", "AMOUNT", "FIXEDRATE",
    "AGE", "CLIENT_SENIORITY_YEARS", "ACCOUNT_SENIORITY_YEARS",
    "DAYS_SINCE_LAST_REVIEW", "NB_COMPTES", "NB_PRODUITS_DISTINCTS",
    "NB_COMPTES_CLOS", "FLAG_INCOHERENCE_CLOTURE",
    "ACCOUNT_CATEGORY", "CURRENCY", "CLOSURE_REASON", "INDUSTRY",
    "PRODUCT_GROUP", "PRODUCT_LINE", "PRODUCT",
    "CUST_OPENING_DATE", "ACCT_OPENING_DATE", "ACCT_CLOSE_DATE",
]

DIM_CLIENT_COLUMNS = [
    "CUSTOMER_NO", "NATIONALITY", "RESIDENCE", "MARITAL_STATUS", "BIRTH_YEAR", "AGE",
    "NATURE_CLIENT", "PARTYCLASS", "LOB", "SCORE_KYC", "COMPLETED_FILE",
]

# Colonnes de dates du fait pour lesquelles on veut une clé étrangère vers
# dim_date (en plus de la date brute, conservée pour lisibilité).
FACT_DATE_FK_COLUMNS = {
    "CUST_OPENING_DATE": "CUST_OPENING_DATE_SK",
    "ACCT_OPENING_DATE": "ACCT_OPENING_DATE_SK",
    "ACCT_CLOSE_DATE": "ACCT_CLOSE_DATE_SK",
}


def _build_dimension_with_sk(
    df: pd.DataFrame, code_col: str, label_col: str, sk_col: str
) -> pd.DataFrame:
    """
    Construit une table de dimension (code métier + libellé) et lui ajoute
    une surrogate key entière (1..N), placée en première colonne. Les codes
    manquants ne donnent pas lieu à une ligne de dimension (ils restent NaN
    côté fait, comme pour une valeur non applicable).
    """
    dim = (
        df[[code_col, label_col]]
        .drop_duplicates()
        .dropna(subset=[code_col])
        .sort_values(code_col)
        .reset_index(drop=True)
    )
    dim.insert(0, sk_col, range(1, len(dim) + 1))
    return dim


def build_star_schema_tables(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """
    Découpe le fait enrichi en un schéma en étoile complet : une table de
    faits + des tables de dimensions, chacune dotée d'une surrogate key
    (suffixe _SK) rattachée au fait par jointure sur le code métier.
    Conçu pour un usage ML : les surrogate keys entières sont plus stables
    et plus efficaces à manipuler que les codes texte lors du feature
    engineering (encodage, jointures répétées, etc.).
    """
    fact_compte_client = df[FACT_COLUMNS].copy()

    # --- Dimension client -------------------------------------------------
    dim_client = (
        df[DIM_CLIENT_COLUMNS]
        .drop_duplicates(subset="CUSTOMER_NO")
        .reset_index(drop=True)
    )
    dim_client.insert(0, "CLIENT_SK", range(1, len(dim_client) + 1))
    fact_compte_client = fact_compte_client.merge(
        dim_client[["CUSTOMER_NO", "CLIENT_SK"]], on="CUSTOMER_NO", how="left"
    )

    # --- Dimensions à faible cardinalité (code + libellé) ------------------
    dim_closure_reason = _build_dimension_with_sk(
        df, "CLOSURE_REASON", "CLOSURE_REASON_LABEL", "CLOSURE_REASON_SK"
    )
    dim_account_category = _build_dimension_with_sk(
        df, "ACCOUNT_CATEGORY", "ACCOUNT_CATEGORY_LABEL", "ACCOUNT_CATEGORY_SK"
    )
    dim_industry = _build_dimension_with_sk(
        df, "INDUSTRY", "INDUSTRY_LABEL", "INDUSTRY_SK"
    )
    dim_currency = _build_dimension_with_sk(
        df, "CURRENCY", "CURRENCY_LABEL", "CURRENCY_SK"
    )

    for dim_df, code_col, sk_col in [
        (dim_closure_reason, "CLOSURE_REASON", "CLOSURE_REASON_SK"),
        (dim_account_category, "ACCOUNT_CATEGORY", "ACCOUNT_CATEGORY_SK"),
        (dim_industry, "INDUSTRY", "INDUSTRY_SK"),
        (dim_currency, "CURRENCY", "CURRENCY_SK"),
    ]:
        fact_compte_client = fact_compte_client.merge(
            dim_df[[code_col, sk_col]], on=code_col, how="left"
        )

    # --- Dimension date -----------------------------------------------------
    # DATE_ID (YYYYMMDD) devient DATE_SK : déjà un entier unique et trié,
    # il joue nativement le rôle de surrogate key pour cette dimension.
    dim_date = build_dim_date(df).rename(columns={"DATE_ID": "DATE_SK"})
    date_lookup = dim_date[["DATE", "DATE_SK"]]
    for date_col, sk_col in FACT_DATE_FK_COLUMNS.items():
        fact_compte_client = fact_compte_client.merge(
            date_lookup.rename(columns={"DATE": date_col, "DATE_SK": sk_col}),
            on=date_col,
            how="left",
        )

    return {
        "fact_compte_client": fact_compte_client,
        "dim_client": dim_client,
        "dim_closure_reason": dim_closure_reason,
        "dim_account_category": dim_account_category,
        "dim_industry": dim_industry,
        "dim_currency": dim_currency,
        "dim_date": dim_date,
    }


def load_to_postgres(tables: dict[str, pd.DataFrame], engine: Engine | None = None, chunksize: int = 10_000) -> None:
    """
    Écrit (ou remplace) chaque table dans l'entrepôt PostgreSQL.
    `chunksize` évite de saturer la mémoire / le réseau sur la table de faits
    (~490 000 lignes) en insérant par lots plutôt qu'en un seul INSERT géant.
    """
    engine = engine or get_engine()
    try:
        for table_name, table_df in tables.items():
            table_df.to_sql(
                table_name,
                engine,
                if_exists="replace",
                index=False,
                chunksize=chunksize,
                method="multi",
            )
            print(f"[load] Table '{table_name}' chargée dans PostgreSQL : {len(table_df):,} lignes")
    finally:
        engine.dispose()
    print(f"[load] Entrepôt PostgreSQL mis à jour : base '{PG_DATABASE}' sur {PG_HOST}:{PG_PORT}")


def export_fact_parquet(fact_df: pd.DataFrame, path: Path = FACT_PARQUET_PATH) -> None:
    """Sauvegarde une copie Parquet du fait, pratique pour le notebook EDA / le ML."""
    fact_df.to_parquet(path, index=False)
    print(f"[load] Fait exporté en Parquet : {path}")


def run_pipeline(nrows: int | None = None) -> None:
    """Enchaîne extract -> transform -> load. Point d'entrée du pipeline complet."""
    df_final = transform_all(nrows=nrows)
    tables = build_star_schema_tables(df_final)
    load_to_postgres(tables)
    export_fact_parquet(tables["fact_compte_client"])
    print("[load] Pipeline ETL terminé avec succès.")


if __name__ == "__main__":
    import sys

    # Usage : python load.py            -> pipeline complet (528 883 lignes)
    #         python load.py 5000       -> test rapide sur un échantillon
    sample_size = int(sys.argv[1]) if len(sys.argv) > 1 else None
    run_pipeline(nrows=sample_size)