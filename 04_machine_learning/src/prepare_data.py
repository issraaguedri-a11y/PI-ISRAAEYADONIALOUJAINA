"""
prepare_data.py
----------------
Construit le jeu de données client (grain = 1 ligne par client) pour la
modélisation du churn, **directement depuis l'entrepôt PostgreSQL**
`churn_dw` (tables `fact_compte_client` + `dim_client` + `dim_industry`),
construit par le pipeline ETL (`01_etl/`) et documenté dans
`02_data_warehouse/` (schéma : `02_data_warehouse/schema/create_tables.sql`,
KPIs : `02_data_warehouse/kpis.md`).

Contrairement à une v1 de ce module qui lisait des CSV bruts sans en-tête,
toute l'agrégation compte -> client est ici faite **côté SQL** (GROUP BY),
ce qui est plus efficace et évite de dupliquer une logique déjà présente
dans le data warehouse.

⚠️ Casse des colonnes en base
------------------------------
Selon la façon dont votre pipeline ETL a chargé les données (méthode
`DataFrame.to_sql()` sans passage en minuscules préalable), les colonnes de
`fact_compte_client` / `dim_client` / `dim_industry` peuvent exister en
PostgreSQL avec leur casse d'origine **majuscule et quotée**
(`"CLIENT_SK"`, `"CUSTOMER_NO"`, ...) plutôt qu'en minuscules non quotées
(`client_sk`, `customer_no`, ...). Un identifiant SQL non quoté est toujours
replié en minuscules par Postgres, d'où l'erreur `UndefinedColumn` si le
code suppose des colonnes minuscules alors qu'elles sont quotées majuscules
en base.

Ce module gère les deux cas automatiquement : `detect_column_case()` inspecte
`information_schema.columns` au démarrage et choisit la bonne casse pour
générer la requête. Vous n'avez rien à modifier à la main, quel que soit le
schéma réellement présent dans votre base.

Cible retenue : `CLIENT_FULL_CHURN` (cf. 02_data_warehouse/kpis.md §1.2)
    = 1 si TOUS les comptes du client sont clôturés (NB_COMPTES_CLOS = NB_COMPTES)
    = 0 sinon
Cette variable est déjà calculée dans `fact_compte_client` par le pipeline
ETL (01_etl/src/transform.py::add_features) ; elle est identique pour
toutes les lignes d'un même client, d'où le MAX() dans le GROUP BY.

Usage :
    python src/prepare_data.py
"""

from __future__ import annotations

from pathlib import Path
import pandas as pd
from sqlalchemy import text

from db import get_engine, read_sql, check_connection

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_PATH = DATA_DIR / "client_churn_dataset.csv"


# ----------------------------------------------------------------------
# Détection automatique de la casse des colonnes en base (voir docstring).
# ----------------------------------------------------------------------
def detect_column_case(engine=None) -> str:
    """
    Inspecte `information_schema.columns` pour la table `fact_compte_client`
    et renvoie "lower" si les colonnes existent en minuscules (ex: client_sk),
    "upper" si elles existent en majuscules (ex: CLIENT_SK), quelle que soit
    la façon dont le pipeline ETL les a créées.
    """
    engine = engine or get_engine()
    query = text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'fact_compte_client' AND column_name ILIKE 'client_sk'"
    )
    with engine.connect() as conn:
        row = conn.execute(query).fetchone()
    if row is None:
        raise RuntimeError(
            "Colonne 'client_sk' (quelle que soit la casse) introuvable dans "
            "fact_compte_client. Vérifiez que le pipeline ETL (01_etl/pipeline.py) "
            "a bien tourné et peuplé l'entrepôt."
        )
    found = row[0]
    case = "lower" if found == found.lower() and found.islower() else "upper"
    print(f"[prepare_data] Casse des colonnes détectée en base : {case} (ex: '{found}')")
    return case


def _q(name: str, case: str) -> str:
    """Quote un identifiant de colonne selon la casse détectée."""
    return f'"{name.upper()}"' if case == "upper" else name.lower()


def build_query(case: str) -> str:
    """Génère la requête SQL d'agrégation en s'adaptant à la casse détectée."""
    f = lambda c: f"f.{_q(c, case)}"
    dc = lambda c: f"dc.{_q(c, case)}"
    di = lambda c: f"di.{_q(c, case)}"

    return f"""
SELECT
    {dc('customer_no')}      AS customer_no,
    {dc('nationality')}      AS nationality,
    {dc('residence')}        AS residence,
    {dc('marital_status')}   AS marital_status,
    {dc('age')}              AS age,
    {dc('nature_client')}    AS nature_client,
    {dc('partyclass')}       AS partyclass,
    {dc('lob')}               AS lob,
    {dc('score_kyc')}        AS score_kyc,
    {dc('completed_file')}   AS completed_file,

    -- Cible
    MAX({f('client_full_churn')})            AS churn,

    -- Comportemental / multi-bancarisation (cf. kpis.md §2.2)
    MAX({f('nb_comptes')})                   AS nb_comptes,
    MAX({f('nb_produits_distincts')})        AS nb_produits_distincts,
    MAX({f('nb_comptes_clos')})              AS nb_comptes_clos,

    -- Ancienneté (cf. kpis.md §1.3 / §2.3)
    MAX({f('client_seniority_years')})       AS anciennete_client_annees,
    AVG({f('account_seniority_years')})      AS anciennete_compte_moy_annees,
    MAX({f('account_seniority_years')})      AS anciennete_compte_max_annees,
    AVG({f('days_since_last_review')})       AS jours_depuis_derniere_revue_moy,

    -- Financier
    SUM({f('acct_balance')})                 AS solde_total,
    AVG({f('acct_balance')})                 AS solde_moyen,
    AVG({f('salary')})                       AS salaire_moyen,
    SUM({f('amount')})                       AS montant_total,
    AVG({f('fixedrate')})                    AS taux_fixe_moyen,

    -- Diversité produits / canaux
    COUNT(DISTINCT {f('currency')})          AS nb_devises,
    COUNT(DISTINCT {f('industry')})          AS nb_secteurs,
    COUNT(DISTINCT {f('branch')})            AS nb_agences,
    MAX(CASE WHEN {f('product_group')} ILIKE '%CRD%' OR {f('product_group')} ILIKE '%ESC.FIN%'
             THEN 1 ELSE 0 END)              AS a_credit,
    MAX(CASE WHEN {f('product_group')} ILIKE '%EPARGNE%' OR {f('product_group')} ILIKE '%PLACEMENT%'
             OR {f('product_group')} ILIKE '%DEPOT%' OR {f('product_group')} ILIKE '%FDI%'
             OR {f('product_group')} ILIKE '%AVC%' THEN 1 ELSE 0 END) AS a_epargne_placement,
    MAX(CASE WHEN {f('product_group')} ILIKE '%CUR.ACCT%' THEN 1 ELSE 0 END) AS a_compte_courant,
    MAX(CASE WHEN {f('product_group')} = 'SAFE.DEPOSIT.BOX' THEN 1 ELSE 0 END) AS a_coffre,

    -- Qualité de données (cf. transform.py::clean_fact)
    MAX({f('flag_incoherence_cloture')}::int) AS flag_incoherence_cloture,

    -- Secteur d'activité principal (valeur la plus fréquente parmi les comptes du client)
    MODE() WITHIN GROUP (ORDER BY {di('industry_label')}) AS secteur_principal

FROM fact_compte_client f
JOIN dim_client dc      ON {f('client_sk')} = {dc('client_sk')}
LEFT JOIN dim_industry di ON {f('industry_sk')} = {di('industry_sk')}
GROUP BY
    {dc('customer_no')}, {dc('nationality')}, {dc('residence')}, {dc('marital_status')}, {dc('age')},
    {dc('nature_client')}, {dc('partyclass')}, {dc('lob')}, {dc('score_kyc')}, {dc('completed_file')}
"""


def build_client_dataset(engine=None) -> pd.DataFrame:
    """Détecte la casse des colonnes, exécute la requête d'agrégation et
    renvoie le DataFrame client x features (colonnes toujours en minuscules
    en sortie, quelle que soit la casse réelle en base)."""
    engine = engine or get_engine()
    case = detect_column_case(engine)
    query = build_query(case)

    print("[prepare_data] Exécution de la requête d'agrégation compte -> client sur PostgreSQL...")
    df = read_sql(query, engine=engine)
    print(f"[prepare_data] {len(df):,} clients récupérés depuis l'entrepôt.")

    # Regroupement des modalités rares (nationalité, résidence, secteur) pour
    # limiter la cardinalité du one-hot encoding en aval (cf. src/train.py).
    for col, top_n in [("nationality", 8), ("residence", 8), ("secteur_principal", 15)]:
        top_values = df[col].value_counts().nlargest(top_n).index
        df[col] = df[col].where(df[col].isin(top_values), other="Autre")

    df["marital_status"] = df["marital_status"].fillna("Non applicable")
    df["completed_file"] = df["completed_file"].fillna("Non")

    return df


def main():
    check_connection()
    df = build_client_dataset()
    df.to_csv(OUTPUT_PATH, index=False)
    print(f"[prepare_data] Dataset sauvegardé : {OUTPUT_PATH}  shape={df.shape}")
    print(df["churn"].value_counts(normalize=True).rename("proportion"))
    return df


if __name__ == "__main__":
    main()