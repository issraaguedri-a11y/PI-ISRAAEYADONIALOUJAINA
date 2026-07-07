"""
load_warehouse.py
------------------
Export des tables du Data Warehouse PostgreSQL (Projet Intégré — Churn Client)
vers des fichiers CSV.

Rôle de ce script : se connecter à l'entrepôt PostgreSQL déjà peuplé (schéma
en étoile : `fact_compte_client` + dimensions), lire chaque table, et
l'enregistrer en CSV dans `02_data_warehouse/output/`. Utile pour :
- alimenter Power BI (ou tout autre outil) directement depuis des fichiers
  plutôt que depuis une connexion live à la base,
- faire une sauvegarde/versionnage ponctuel de l'état de l'entrepôt,
- partager un extrait des données transformées sans donner accès à la base.

Ce script ne fait AUCUNE écriture dans PostgreSQL : il est uniquement en
lecture (SELECT * FROM ...).

Prérequis :
- PostgreSQL accessible et déjà peuplé (variables d'environnement ci-dessous).
- Dépendances : pandas, sqlalchemy, psycopg2-binary.

Usage :
    python 02_data_warehouse/load/load_warehouse.py                  # toutes les tables
    python 02_data_warehouse/load/load_warehouse.py --tables dim_client fact_compte_client
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import Engine

# ------------------------------------------------------------------
# Chemins
# ------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parents[2]
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"

# ------------------------------------------------------------------
# Configuration PostgreSQL
# ------------------------------------------------------------------
PG_HOST = os.environ.get("PGHOST", "localhost")
PG_PORT = os.environ.get("PGPORT", "5432")
PG_DATABASE = os.environ.get("PGDATABASE", "churn_dw")
PG_USER = os.environ.get("PGUSER", "postgres")
PG_PASSWORD = os.environ.get("PGPASSWORD", "postgres")

# Tables du schéma en étoile, dans un ordre lisible (dimensions puis fait).
# Utilisé par défaut si --tables n'est pas précisé.
DEFAULT_TABLES = [
    "dim_date",
    "dim_client",
    "dim_closure_reason",
    "dim_account_category",
    "dim_industry",
    "dim_currency",
    "fact_compte_client",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Exporte les tables du Data Warehouse PostgreSQL en fichiers CSV."
    )
    parser.add_argument(
        "--tables",
        nargs="+",
        default=None,
        help="Liste des tables à exporter (par défaut : toutes les tables du schéma en étoile).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help=f"Dossier de sortie des CSV (défaut : {OUTPUT_DIR}).",
    )
    return parser.parse_args()


def get_engine() -> Engine:
    url = f"postgresql+psycopg2://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DATABASE}"
    return create_engine(url)


def _existing_tables(engine: Engine) -> set[str]:
    """Liste les tables réellement présentes dans le schéma public, pour éviter une erreur peu claire."""
    return set(inspect(engine).get_table_names(schema="public"))


def export_table_to_csv(engine: Engine, table_name: str, output_dir: Path) -> None:
    """Lit une table entière depuis PostgreSQL et l'enregistre en CSV."""
    df = pd.read_sql_table(table_name, engine)
    output_path = output_dir / f"{table_name}.csv"
    df.to_csv(output_path, index=False)
    print(f"[load_warehouse] Table '{table_name}' exportée : {output_path} ({len(df):,} lignes)")


def export_warehouse_to_csv(tables: list[str] | None = None, output_dir: Path = OUTPUT_DIR) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    engine = get_engine()
    try:
        tables_to_export = tables or DEFAULT_TABLES

        available = _existing_tables(engine)
        missing = [t for t in tables_to_export if t not in available]
        if missing:
            raise ValueError(
                f"Table(s) introuvable(s) dans la base '{PG_DATABASE}' : {missing}\n"
                f"Tables disponibles : {sorted(available)}"
            )

        for table_name in tables_to_export:
            export_table_to_csv(engine, table_name, output_dir)
    finally:
        engine.dispose()

    print(f"[load_warehouse] Export terminé : {len(tables or DEFAULT_TABLES)} table(s) -> {output_dir}")


def main() -> None:
    args = parse_args()
    export_warehouse_to_csv(tables=args.tables, output_dir=args.output_dir)


if __name__ == "__main__":
    main()