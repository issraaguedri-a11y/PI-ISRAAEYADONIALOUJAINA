"""
pipeline.py
-----------
Orchestrateur principal du pipeline ETL du Projet Intégré (Churn Client).

Ce script ne contient aucune logique métier : il se contente d'enchaîner
extract -> transform -> load (définis dans 01_etl/src/) et d'afficher un
résumé clair de l'exécution. C'est le point d'entrée unique à lancer pour
reconstruire l'entrepôt de bout en bout.

Usage :
    python 01_etl/pipeline.py             # pipeline complet (528 883 lignes)
    python 01_etl/pipeline.py --sample 5000   # test rapide sur un échantillon
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Permet d'importer extract.py / transform.py / load.py depuis 01_etl/src
SRC_DIR = Path(__file__).resolve().parent / "src"
sys.path.insert(0, str(SRC_DIR))

from load import run_pipeline  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pipeline ETL complet : extraction, nettoyage, enrichissement, chargement dans l'entrepôt DuckDB."
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=None,
        help="Nombre de lignes à traiter (utile pour un test rapide). Par défaut : tout le fichier.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print("=" * 60)
    print("PIPELINE ETL — Projet Intégré (Churn Client)")
    print("=" * 60)
    if args.sample:
        print(f"Mode échantillon : {args.sample:,} lignes\n")
    else:
        print("Mode complet : traitement de l'intégralité du fichier\n")

    start = time.time()
    try:
        run_pipeline(nrows=args.sample)
    except Exception as exc:
        print(f"\n[ERREUR] Le pipeline a échoué : {exc}")
        sys.exit(1)

    elapsed = time.time() - start
    print("\n" + "=" * 60)
    print(f"Pipeline terminé avec succès en {elapsed:.1f} secondes.")
    print("=" * 60)


if __name__ == "__main__":
    main()