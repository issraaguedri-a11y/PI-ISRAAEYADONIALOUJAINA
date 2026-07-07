"""
extract.py
----------
Étape EXTRACT du pipeline ETL du Projet Intégré (Churn Client).

Responsabilités :
- Lire le fichier principal `data_churn.csv` (528 883 lignes, 34 colonnes).
- Lire les tables de dimensions Excel utiles à l'enrichissement
  (`dim_CATEGORY.ACCOUNT`, `dim_CURRENCY`, `dim_Closure_reason`, `dim_INDUSTRY`).
- Ne fait AUCUN nettoyage ni transformation : ce script se contente de charger
  les données brutes en mémoire et de vérifier qu'elles sont lisibles.

Ce module expose des fonctions réutilisables (par transform.py / load.py) et
peut aussi être exécuté seul pour un contrôle rapide :

    python extract.py
"""

from pathlib import Path
import pandas as pd

# ------------------------------------------------------------------
# Chemins
# ------------------------------------------------------------------
# 01_etl/src/extract.py -> on remonte de 2 niveaux pour atteindre la racine du repo
BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"

RAW_CSV_PATH = DATA_DIR / "data_churn.txt"

DIM_FILES = {
    "account_category": DATA_DIR / "dim_CATEGORY.ACCOUNT.xlsx",
    "currency": DATA_DIR / "dim_CURRENCY.xlsx",
    "closure_reason": DATA_DIR / "dim_Closure_reason.xlsx",
    "industry": DATA_DIR / "dim_INDUSTRY.xlsx",
}

# Colonnes attendues dans le fichier principal (sert de garde-fou :
# si le schéma change, on le sait immédiatement au lieu de planter plus loin)
EXPECTED_COLUMNS = [
    "CUSTOMER_NO", "ACCOUNT_NO", "NATIONALITY", "RESIDENCE", "MARITAL_STATUS",
    "CUST_OPENING_DATE", "DATE_OF_BIRTH", "NATURE_CLIENT", "BRANCH", "SCORE_KYC",
    "COMPLETED_FILE", "LAST_REVIEW_DATE", "NEXT__REVIEW_DATE", "ACCOUNT_STATUS",
    "ACCT_OPENING_DATE", "ACCOUNT_CATEGORY", "ACCOUNT_TYPE_DESC", "CURRENCY",
    "ACCT_CLOSE_DATE", "CLOSURE_REASON", "ACCT_BALANCE", "INDUSTRY", "SALARY",
    "PRODUCT_GROUP", "PRODUCT_LINE", "PRODUCT", "ACCOUNTNATURE", "STARTDATE",
    "MATURITYDATE", "AMOUNT", "FIXEDRATE", "PRODUCT_STATUS", "PARTYCLASS", "LOB",
]

# Dtypes forcés à la lecture pour éviter les inférences fantaisistes de pandas
# (les identifiants et codes doivent rester des chaînes, pas des nombres/floats)
RAW_DTYPES = {
    "CUSTOMER_NO": "string",
    "ACCOUNT_NO": "string",
    "NATIONALITY": "string",
    "RESIDENCE": "string",
    "MARITAL_STATUS": "string",
    "NATURE_CLIENT": "string",
    "BRANCH": "string",
    "SCORE_KYC": "string",
    "COMPLETED_FILE": "string",
    "ACCOUNT_STATUS": "string",
    "ACCOUNT_CATEGORY": "string",
    "ACCOUNT_TYPE_DESC": "string",
    "CURRENCY": "string",
    "CLOSURE_REASON": "string",
    "INDUSTRY": "string",
    "PRODUCT_GROUP": "string",
    "PRODUCT_LINE": "string",
    "PRODUCT": "string",
    "ACCOUNTNATURE": "string",
    "PRODUCT_STATUS": "string",
    "PARTYCLASS": "string",
    "LOB": "string",
}


def extract_raw_data(csv_path: Path = RAW_CSV_PATH, nrows: int | None = None) -> pd.DataFrame:
    """
    Charge le fichier principal data_churn.csv tel quel (sans nettoyage).

    Parameters
    ----------
    csv_path : Path
        Emplacement du CSV brut.
    nrows : int, optional
        Limiter le nombre de lignes lues (utile pour tester rapidement le
        pipeline sur un échantillon avant de lancer les 528 883 lignes).

    Returns
    -------
    pd.DataFrame
    """
    if not csv_path.exists():
        raise FileNotFoundError(
            f"Fichier introuvable : {csv_path}\n"
            "-> Vérifiez que Git LFS est installé et que `git lfs pull` a bien "
            "été exécuté (voir data/README.md)."
        )

    df = pd.read_csv(
        csv_path,
        dtype=RAW_DTYPES,
        low_memory=False,
        nrows=nrows,
    )

    missing_cols = set(EXPECTED_COLUMNS) - set(df.columns)
    extra_cols = set(df.columns) - set(EXPECTED_COLUMNS)
    if missing_cols:
        raise ValueError(f"Colonnes manquantes par rapport au schéma attendu : {missing_cols}")
    if extra_cols:
        print(f"[extract] Avertissement : colonnes inattendues présentes : {extra_cols}")

    print(f"[extract] data_churn.csv chargé : {df.shape[0]:,} lignes / {df.shape[1]} colonnes")
    return df


def extract_dimensions(dim_files: dict[str, Path] = DIM_FILES) -> dict[str, pd.DataFrame]:
    """
    Charge les tables de dimensions Excel utilisées pour enrichir le fait
    (jointures faites plus tard dans transform.py).

    Returns
    -------
    dict[str, pd.DataFrame]
        Un DataFrame par dimension, indexé par nom logique
        ("account_category", "currency", "closure_reason", "industry").
    """
    dimensions = {}
    for name, path in dim_files.items():
        if not path.exists():
            raise FileNotFoundError(f"Table de dimension introuvable : {path}")
        dimensions[name] = pd.read_excel(path)
        print(f"[extract] {name} chargé depuis {path.name} : {dimensions[name].shape[0]} lignes")
    return dimensions


def extract_all(nrows: int | None = None) -> dict:
    """
    Point d'entrée unique utilisé par transform.py : renvoie un dictionnaire
    contenant le fait brut et toutes les dimensions brutes.
    """
    return {
        "fact_raw": extract_raw_data(nrows=nrows),
        "dimensions": extract_dimensions(),
    }


if __name__ == "__main__":
    # Contrôle rapide en ligne de commande : lit un échantillon de 5000 lignes
    # pour vérifier que les chemins et le schéma sont corrects sans attendre
    # le chargement complet du fichier de 110 Mo.
    data = extract_all(nrows=5000)
    print("\nAperçu du fait brut :")
    print(data["fact_raw"].head())
    print("\nDimensions chargées :", list(data["dimensions"].keys()))