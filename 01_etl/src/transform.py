"""
transform.py
------------
Étape TRANSFORM du pipeline ETL du Projet Intégré (Churn Client).

Responsabilités :
- Nettoyer le fait brut (doublons, valeurs "NULL" textuelles, types, dates YYYYMMDD).
- Enrichir le fait avec les libellés des dimensions (jointures).
- Calculer les features dérivées utiles au ML et au BI (âge, ancienneté client,
  ancienneté compte, indicateur de complétude, etc.).
- Construire la variable cible `CHURN`.

Ce module s'appuie sur extract.py pour récupérer les données brutes, et expose
une fonction `transform_all()` réutilisée par load.py.

Exécution directe (test rapide sur un échantillon) :
    python transform.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from extract import extract_all

# ------------------------------------------------------------------
# Constantes de nettoyage
# ------------------------------------------------------------------
# Valeurs textuelles qui représentent en réalité un manquant dans ce SI bancaire
NULL_LIKE_STRINGS = {"", "NULL", "null", "None", "NaN", "N/A", "NA", "-"}

DATE_COLUMNS = [
    "CUST_OPENING_DATE", "LAST_REVIEW_DATE", "NEXT__REVIEW_DATE",
    "ACCT_OPENING_DATE", "ACCT_CLOSE_DATE", "STARTDATE", "MATURITYDATE",
]

REFERENCE_DATE = pd.Timestamp("2026-07-05")  # date de traitement du pipeline

# Date plancher de la dimension DATE : les dates antérieures à 1900 observées
# dans le fait sont des erreurs de saisie/anonymisation (ex: années à 3 ou 4
# chiffres tronquées) et n'ont aucune valeur analytique -> on les exclut pour
# alléger la dimension au lieu de générer des lignes non exploitables.
MIN_DATE = pd.Timestamp("1900-01-01")

# Age maximum plausible pour un client (au-delà, on considère qu'il s'agit
# d'une erreur d'anonymisation / de saisie de l'année de naissance).
MAX_AGE = 100

# Code NATURE_CLIENT identifiant une personne morale (entreprise) dans ce SI.
# Pour ces clients, les attributs propres aux personnes physiques (état civil,
# date de naissance, salaire...) n'ont pas de sens et ne doivent pas être
# traités comme des valeurs manquantes "classiques".
LEGAL_ENTITY_CODE = "PM"

# Code/libellé dédiés aux comptes clôturés dont le motif réel n'a pas été
# renseigné dans le SI d'origine. Volontairement distinct du code "Autre"
# (choisi explicitement par le client), pour ne pas fausser la distribution
# du motif de clôture côté ML/BI.
UNKNOWN_CLOSURE_REASON_CODE = "UNKNOWN"
UNKNOWN_CLOSURE_REASON_LABEL = "Non renseigné"

# Libellés (en français) pour la dimension DATE
MONTH_NAMES_FR = {
    1: "Janvier", 2: "Février", 3: "Mars", 4: "Avril", 5: "Mai", 6: "Juin",
    7: "Juillet", 8: "Août", 9: "Septembre", 10: "Octobre", 11: "Novembre", 12: "Décembre",
}
DAY_NAMES_FR = {
    0: "Lundi", 1: "Mardi", 2: "Mercredi", 3: "Jeudi", 4: "Vendredi", 5: "Samedi", 6: "Dimanche",
}


# ------------------------------------------------------------------
# Nettoyage
# ------------------------------------------------------------------
def _clean_string_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Uniformise les colonnes texte : trim + remplacement des pseudo-NULL par NaN."""
    str_cols = df.select_dtypes(include=["string", "object"]).columns
    for col in str_cols:
        df[col] = df[col].astype("string").str.strip()
        df[col] = df[col].mask(df[col].isin(NULL_LIKE_STRINGS))
    return df


def _strip_float_suffix(series: pd.Series) -> pd.Series:
    """
    Certains codes numériques arrivent formatés en `"3023.0"` côté fait alors
    que la dimension correspondante utilise `"3023"` (sans décimale).
    Sans cette normalisation, la jointure échoue silencieusement et renvoie
    des libellés vides (cas réel constaté sur ACCOUNT_CATEGORY).
    """
    return series.astype("string").str.replace(r"\.0$", "", regex=True)


def _parse_yyyymmdd(series: pd.Series) -> pd.Series:
    """
    Convertit une colonne de dates au format numérique YYYYMMDD (ex: 20250905.0)
    en véritable dtype datetime64. Les valeurs invalides deviennent NaT plutôt
    que de faire planter le pipeline.
    """
    as_str = series.astype("string").str.replace(r"\.0$", "", regex=True)
    return pd.to_datetime(as_str, format="%Y%m%d", errors="coerce")


def _parse_dates(df: pd.DataFrame) -> pd.DataFrame:
    for col in DATE_COLUMNS:
        if col in df.columns:
            df[col] = _parse_yyyymmdd(df[col])
    return df


def _parse_birth_year(df: pd.DataFrame) -> pd.DataFrame:
    """
    DATE_OF_BIRTH a été anonymisée pour ne conserver que l'année (ex: 1969).
    On la garde comme année entière plutôt que comme date complète.
    """
    df["BIRTH_YEAR"] = pd.to_numeric(df["DATE_OF_BIRTH"], errors="coerce").astype("Int64")
    return df


def clean_fact(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Applique les règles de nettoyage sur le fait brut :
    - dédoublonnage
    - normalisation des chaînes / valeurs manquantes
    - typage des dates
    - typage des montants
    """
    df = df_raw.copy()

    before = len(df)
    df = df.drop_duplicates()
    print(f"[transform] Doublons supprimés : {before - len(df)}")

    df = _clean_string_columns(df)
    df = _parse_birth_year(df)
    df = _parse_dates(df)

    # COMPLETED_FILE : l'absence de valeur signifie en pratique que le
    # dossier client n'a pas été complété -> on l'explicite par "Non"
    # plutôt que de laisser un NaN ambigu.
    df["COMPLETED_FILE"] = df["COMPLETED_FILE"].fillna("Non")

    # Personnes morales (entreprises) : des attributs comme l'état civil
    # n'ont pas de sens pour une entreprise. Ce ne sont pas des valeurs
    # manquantes à traiter comme telles : on les marque explicitement
    # "Non applicable" pour les distinguer d'un vrai défaut de saisie
    # chez les personnes physiques.
    is_legal_entity = df["NATURE_CLIENT"] == LEGAL_ENTITY_CODE
    df.loc[is_legal_entity, "MARITAL_STATUS"] = (
        df.loc[is_legal_entity, "MARITAL_STATUS"].fillna("Non applicable")
    )

    # Normalisation des codes numériques mal formatés (ex: "3023.0" -> "3023")
    # pour que les jointures avec les dimensions fonctionnent réellement.
    df["ACCOUNT_CATEGORY"] = _strip_float_suffix(df["ACCOUNT_CATEGORY"])

    numeric_cols = ["ACCT_BALANCE", "SALARY", "AMOUNT", "FIXEDRATE"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # FIXEDRATE : l'absence de taux fixe correspond aux comptes non rémunérés
    # (comptes courants...) et non à un défaut de saisie -> on assimile
    # l'absence de valeur à un taux de 0%.
    df["FIXEDRATE"] = df["FIXEDRATE"].fillna(0)

    # SALARY, ACCT_BALANCE, AMOUNT : imputation par le mode (valeur la plus
    # fréquente) plutôt que de laisser un NaN. Ces trois variables sont très
    # asymétriques (quelques montants très élevés tirent fortement la moyenne
    # vers le haut), donc la moyenne serait un mauvais choix. Constat sur les
    # données : le mode de ACCT_BALANCE et AMOUNT vaut 0, ce qui correspond
    # justement aux comptes/produits sans solde ou montant applicable (ex:
    # comptes courants) — cohérent avec le traitement fait sur FIXEDRATE
    # ci-dessus. Pour SALARY, le mode coïncide avec la médiane, le choix est
    # donc neutre. Si un besoin de robustesse supplémentaire se fait sentir
    # (ex: analyses de revenu moyen), la médiane resterait l'alternative
    # recommandée à la moyenne, sans changer l'interprétation du churn.
    for col in ["SALARY", "ACCT_BALANCE", "AMOUNT"]:
        mode_val = df[col].mode(dropna=True)
        if not mode_val.empty:
            df[col] = df[col].fillna(mode_val.iloc[0])

    # PRODUCT_LINE / PRODUCT : absence de valeur -> "0" (plutôt qu'un NaN),
    # à la demande du projet.
    df["PRODUCT_LINE"] = df["PRODUCT_LINE"].fillna("0")
    df["PRODUCT"] = df["PRODUCT"].fillna("0")

    # Incohérence signalée dans la doc : date de clôture renseignée sans statut
    # "Closed" (ou l'inverse). On garde une colonne de flag plutôt que de
    # supprimer la ligne, pour rester traçable dans le rapport.
    df["FLAG_INCOHERENCE_CLOTURE"] = (
        df["ACCT_CLOSE_DATE"].notna() & ~df["ACCOUNT_STATUS"].str.contains("Closed", case=False, na=False)
    ) | (
        df["ACCOUNT_STATUS"].str.contains("Closed", case=False, na=False) & df["ACCT_CLOSE_DATE"].isna()
    )

    return df


# ------------------------------------------------------------------
# Enrichissement (jointures avec les dimensions)
# ------------------------------------------------------------------
def enrich_with_dimensions(df: pd.DataFrame, dimensions: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Ajoute les libellés lisibles des dimensions au fait, sans perdre les codes bruts."""
    df = df.copy()

    dim_category = dimensions["account_category"].rename(
        columns={"CATEGORY_id": "ACCOUNT_CATEGORY", "CATEGORY DESCRIPTION": "ACCOUNT_CATEGORY_LABEL"}
    )[["ACCOUNT_CATEGORY", "ACCOUNT_CATEGORY_LABEL"]]
    dim_category["ACCOUNT_CATEGORY"] = dim_category["ACCOUNT_CATEGORY"].astype("string")

    dim_currency = dimensions["currency"].rename(
        columns={"CURRENCY_CODE": "CURRENCY", "CCY_NAME": "CURRENCY_LABEL"}
    )[["CURRENCY", "CURRENCY_LABEL"]]

    dim_closure_raw = dimensions["closure_reason"].copy()
    # La clé RECID du fichier dimension est préfixée ("CLOSURE.REASON*ATB.REASON.13")
    # alors que les données anonymisées ne conservent que le suffixe, avec en
    # plus le remplacement ATB -> BANK appliqué par anonymize.py. Le fichier
    # dimension, lui, n'a PAS été anonymisé ("copié tel quel" selon le script).
    # On reproduit donc ici la même transformation pour que la clé matche :
    dim_closure_raw["CLOSURE_REASON"] = (
        dim_closure_raw["RECID"]
        .astype("string")
        .str.split("*").str[-1]
        .str.replace(r"\bATB\b", "BANK", regex=True, case=False)
    )
    dim_closure = dim_closure_raw.rename(columns={"DESCRIPTION": "CLOSURE_REASON_LABEL"})[
        ["CLOSURE_REASON", "CLOSURE_REASON_LABEL"]
    ]

    dim_industry = dimensions["industry"].rename(
        columns={"INDUSTRY_CODE": "INDUSTRY", "INDUSTRY DESCRIPTION": "INDUSTRY_LABEL"}
    )[["INDUSTRY", "INDUSTRY_LABEL"]]
    dim_industry["INDUSTRY"] = dim_industry["INDUSTRY"].astype("string")

    df = df.merge(dim_category, on="ACCOUNT_CATEGORY", how="left")
    df = df.merge(dim_currency, on="CURRENCY", how="left")
    df = df.merge(dim_closure, on="CLOSURE_REASON", how="left")
    df = df.merge(dim_industry, on="INDUSTRY", how="left")

    # CLOSURE_REASON : la grande majorité des valeurs manquantes vient de
    # comptes encore ouverts, pour lesquels l'absence de raison de clôture
    # est normale (pas une donnée manquante) -> on ne touche pas à ces lignes.
    # Pour un compte réellement clôturé sans raison renseignée, on NE remplit
    # PAS avec "Autre" : ce serait mélanger "le client a explicitement choisi
    # Autre" avec "on ne sait pas pourquoi" et fausserait la distribution
    # réelle du motif de clôture (utilisée potentiellement comme feature ou
    # cible en ML). On introduit donc un code dédié, distinct de "Autre".
    is_closed = df["ACCOUNT_STATUS"].str.contains("Closed", case=False, na=False)
    missing_reason_closed = is_closed & df["CLOSURE_REASON"].isna()
    df.loc[missing_reason_closed, "CLOSURE_REASON"] = UNKNOWN_CLOSURE_REASON_CODE
    df.loc[missing_reason_closed, "CLOSURE_REASON_LABEL"] = UNKNOWN_CLOSURE_REASON_LABEL

    # ACCOUNT_CATEGORY_LABEL : soit le code n'a pas de correspondance dans la
    # dimension, soit la description est elle-même vide côté dimension
    # (cas réel constaté sur plusieurs codes de dim_account_category).
    # On explicite ces deux cas par "Non disponible" plutôt que de laisser NaN.
    df["ACCOUNT_CATEGORY_LABEL"] = df["ACCOUNT_CATEGORY_LABEL"].fillna("Non disponible")

    return df


def _cap_and_impute_age(df: pd.DataFrame, max_age: int = MAX_AGE) -> pd.DataFrame:
    """
    Nettoie la variable AGE calculée à partir de l'année de naissance anonymisée :
    - une valeur négative (naissance dans le futur, erreur d'anonymisation)
      devient manquante ;
    - une valeur supérieure à `max_age` (100 ans) est plafonnée à `max_age`,
      plutôt que supprimée, pour ne pas perdre la ligne ;
    - les valeurs manquantes restantes (dont celles issues du cas précédent
      et les BIRTH_YEAR absents) sont imputées par le mode, c.-à-d. l'âge le
      plus fréquent observé dans le portefeuille, pour rester statistiquement
      neutre côté ML/BI.
    """
    df = df.copy()
    df.loc[df["AGE"] < 0, "AGE"] = pd.NA
    df.loc[df["AGE"] > max_age, "AGE"] = max_age

    age_mode = df["AGE"].mode(dropna=True)
    if not age_mode.empty:
        df["AGE"] = df["AGE"].fillna(age_mode.iloc[0])

    return df


# ------------------------------------------------------------------
# Feature engineering
# ------------------------------------------------------------------
def add_features(df: pd.DataFrame, reference_date: pd.Timestamp = REFERENCE_DATE) -> pd.DataFrame:
    """Ajoute les variables dérivées identifiées dans 2_description_donnees.md."""
    df = df.copy()

    # Âge du client (à partir de l'année de naissance anonymisée),
    # plafonné à MAX_AGE et imputé par le mode pour les valeurs manquantes.
    df["AGE"] = reference_date.year - df["BIRTH_YEAR"]
    df = _cap_and_impute_age(df)

    # Ancienneté client / compte, en années
    df["CLIENT_SENIORITY_YEARS"] = (reference_date - df["CUST_OPENING_DATE"]).dt.days / 365.25
    df["ACCOUNT_SENIORITY_YEARS"] = (reference_date - df["ACCT_OPENING_DATE"]).dt.days / 365.25

    # Ancienneté de la dernière revue KYC
    df["DAYS_SINCE_LAST_REVIEW"] = (reference_date - df["LAST_REVIEW_DATE"]).dt.days

    # Variable cible : churn = clôture du compte (au niveau ligne compte-produit)
    df["CHURN"] = df["ACCOUNT_STATUS"].str.contains("Closed", case=False, na=False).astype(int)

    # Variables comportementales agrégées au niveau client.
    # Attention : un même compte peut apparaître sur plusieurs lignes (un par
    # produit). NB_COMPTES_CLOS doit donc compter des ACCOUNT_NO distincts en
    # statut fermé, PAS le nombre de lignes CHURN=1 (sinon un compte à 2
    # produits fermés serait compté 2 fois, faussant la comparaison avec
    # NB_COMPTES et rendant CLIENT_FULL_CHURN incalculable correctement).
    closed_accounts = df.loc[df["CHURN"] == 1, ["CUSTOMER_NO", "ACCOUNT_NO"]].drop_duplicates()
    nb_comptes_clos = (
        closed_accounts.groupby("CUSTOMER_NO")["ACCOUNT_NO"]
        .nunique()
        .rename("NB_COMPTES_CLOS")
    )

    client_agg = (
        df.groupby("CUSTOMER_NO")
        .agg(
            NB_COMPTES=("ACCOUNT_NO", "nunique"),
            NB_PRODUITS_DISTINCTS=("PRODUCT", "nunique"),
        )
        .reset_index()
        .merge(nb_comptes_clos, on="CUSTOMER_NO", how="left")
    )
    client_agg["NB_COMPTES_CLOS"] = client_agg["NB_COMPTES_CLOS"].fillna(0).astype(int)
    client_agg["CLIENT_FULL_CHURN"] = (
        client_agg["NB_COMPTES_CLOS"] == client_agg["NB_COMPTES"]
    ).astype(int)

    df = df.merge(client_agg, on="CUSTOMER_NO", how="left")

    return df


# ------------------------------------------------------------------
# Dimension DATE
# ------------------------------------------------------------------
def build_dim_date(df: pd.DataFrame, date_columns: list[str] = DATE_COLUMNS) -> pd.DataFrame:
    """
    Construit la dimension DATE du modèle en étoile à partir de toutes les
    dates distinctes rencontrées dans le fait (ouverture client, ouverture
    et clôture de compte, revues KYC, dates de dépôt/échéance...).

    Chaque date obtient un DATE_ID au format entier YYYYMMDD, utilisable
    comme clé de jointure côté fait, ainsi que des attributs calendaires
    classiques (année, trimestre, mois, jour, jour de semaine...).
    """
    existing_cols = [c for c in date_columns if c in df.columns]
    all_dates = pd.concat([df[c] for c in existing_cols], ignore_index=True)
    all_dates = all_dates.dropna().drop_duplicates()
    all_dates = all_dates[all_dates >= MIN_DATE].sort_values().reset_index(drop=True)

    dim_date = pd.DataFrame({"DATE": all_dates})
    dim_date["DATE_ID"] = dim_date["DATE"].dt.strftime("%Y%m%d").astype(int)
    dim_date["YEAR"] = dim_date["DATE"].dt.year
    dim_date["QUARTER"] = dim_date["DATE"].dt.quarter
    dim_date["MONTH"] = dim_date["DATE"].dt.month
    dim_date["MONTH_NAME"] = dim_date["MONTH"].map(MONTH_NAMES_FR)
    dim_date["DAY"] = dim_date["DATE"].dt.day
    dim_date["DAY_OF_WEEK"] = dim_date["DATE"].dt.dayofweek  # 0 = lundi
    dim_date["DAY_NAME"] = dim_date["DAY_OF_WEEK"].map(DAY_NAMES_FR)
    dim_date["WEEK_OF_YEAR"] = dim_date["DATE"].dt.isocalendar().week.astype(int)
    dim_date["IS_WEEKEND"] = dim_date["DAY_OF_WEEK"].isin([5, 6])
    dim_date["IS_MONTH_END"] = dim_date["DATE"].dt.is_month_end
    dim_date["IS_YEAR_END"] = dim_date["DATE"].dt.is_year_end

    return dim_date[
        [
            "DATE_ID", "DATE", "YEAR", "QUARTER", "MONTH", "MONTH_NAME", "DAY",
            "DAY_OF_WEEK", "DAY_NAME", "WEEK_OF_YEAR", "IS_WEEKEND", "IS_MONTH_END", "IS_YEAR_END",
        ]
    ]


# ------------------------------------------------------------------
# Orchestration de la transformation
# ------------------------------------------------------------------
def transform_all(nrows: int | None = None) -> pd.DataFrame:
    """
    Enchaîne extraction -> nettoyage -> enrichissement -> feature engineering.
    Renvoie le fait final prêt à être chargé dans l'entrepôt (load.py).
    """
    raw = extract_all(nrows=nrows)
    df = clean_fact(raw["fact_raw"])
    df = enrich_with_dimensions(df, raw["dimensions"])
    df = add_features(df)

    print(f"[transform] Fait final : {df.shape[0]:,} lignes / {df.shape[1]} colonnes")
    print(f"[transform] Taux de churn (lignes compte-produit) : {df['CHURN'].mean():.2%}")

    return df


if __name__ == "__main__":
    df_final = transform_all(nrows=5000)
    print("\nAperçu du fait transformé :")
    print(df_final[["CUSTOMER_NO", "ACCOUNT_NO", "AGE", "CLIENT_SENIORITY_YEARS", "CHURN"]].head())