"""
queries.py
----------
Requêtes SQL sur l'entrepôt `churn_dw`, réutilisant exactement la même
logique de détection de casse des colonnes que
`04_machine_learning/src/prepare_data.py` (les colonnes peuvent être en
minuscules `client_sk` ou en MAJUSCULES quotées `"CLIENT_SK"` selon la façon
dont le pipeline ETL a chargé l'entrepôt).
"""

from __future__ import annotations

import streamlit as st
from sqlalchemy import text

from utils.db import get_engine, read_sql


@st.cache_data(ttl=3600, show_spinner=False)
def detect_column_case() -> str:
    """Renvoie 'lower' ou 'upper' selon la casse réelle des colonnes en base."""
    engine = get_engine()
    query = text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'fact_compte_client' AND column_name ILIKE 'client_sk'"
    )
    with engine.connect() as conn:
        row = conn.execute(query).fetchone()
    if row is None:
        raise RuntimeError(
            "Colonne 'client_sk' introuvable dans fact_compte_client. "
            "L'entrepôt PostgreSQL est-il bien peuplé (01_etl/pipeline.py) ?"
        )
    found = row[0]
    return "lower" if found == found.lower() and found.islower() else "upper"


def _q(name: str, case: str) -> str:
    return f'"{name.upper()}"' if case == "upper" else name.lower()


def _client_dataset_query(case: str) -> str:
    """Même requête d'agrégation compte -> client que
    04_machine_learning/src/prepare_data.py::build_query(), dupliquée ici pour
    que 05_web_app reste un module autonome et déployable indépendamment
    (pas de dépendance croisée entre les deux dossiers du repo)."""
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

    MAX({f('client_full_churn')})            AS churn,
    MAX({f('nb_comptes')})                   AS nb_comptes,
    MAX({f('nb_produits_distincts')})        AS nb_produits_distincts,
    MAX({f('nb_comptes_clos')})              AS nb_comptes_clos,

    MAX({f('client_seniority_years')})       AS anciennete_client_annees,
    AVG({f('account_seniority_years')})      AS anciennete_compte_moy_annees,
    MAX({f('account_seniority_years')})      AS anciennete_compte_max_annees,
    AVG({f('days_since_last_review')})       AS jours_depuis_derniere_revue_moy,

    SUM({f('acct_balance')})                 AS solde_total,
    AVG({f('acct_balance')})                 AS solde_moyen,
    AVG({f('salary')})                       AS salaire_moyen,
    SUM({f('amount')})                       AS montant_total,
    AVG({f('fixedrate')})                    AS taux_fixe_moyen,

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

    MAX({f('flag_incoherence_cloture')}::int) AS flag_incoherence_cloture,
    MODE() WITHIN GROUP (ORDER BY {di('industry_label')}) AS secteur_principal,
    MAX({f('branch')})                        AS agence_principale,
    MAX({f('account_status')})                AS dernier_statut_connu

FROM fact_compte_client f
JOIN dim_client dc      ON {f('client_sk')} = {dc('client_sk')}
LEFT JOIN dim_industry di ON {f('industry_sk')} = {di('industry_sk')}
{{where_clause}}
GROUP BY
    {dc('customer_no')}, {dc('nationality')}, {dc('residence')}, {dc('marital_status')}, {dc('age')},
    {dc('nature_client')}, {dc('partyclass')}, {dc('lob')}, {dc('score_kyc')}, {dc('completed_file')}
"""


@st.cache_data(ttl=600, show_spinner="Chargement des clients depuis l'entrepôt...")
def get_client_dataset(limit: int | None = None):
    """Jeu de données client complet (mêmes features que le modèle de churn)."""
    case = detect_column_case()
    query = _client_dataset_query(case).format(where_clause="")
    if limit:
        query += f"\nLIMIT {int(limit)}"
    return read_sql(query)


@st.cache_data(ttl=600, show_spinner=False)
def get_client_by_id(customer_no: str):
    """Récupère les features d'un client précis par son CUSTOMER_NO."""
    case = detect_column_case()
    where = f"WHERE {_q('customer_no', case) if case=='lower' else 'dc.\"CUSTOMER_NO\"'} = :customer_no"
    # Reconstruction propre du WHERE avec alias dc, quelle que soit la casse :
    where = f"WHERE dc.{_q('customer_no', case)} = :customer_no"
    query = _client_dataset_query(case).format(where_clause=where)
    return read_sql(query, params={"customer_no": customer_no})


@st.cache_data(ttl=600, show_spinner=False)
def list_customer_ids(search: str = "", limit: int = 50):
    """Liste de CUSTOMER_NO pour l'auto-complétion du formulaire de recherche."""
    case = detect_column_case()
    col = _q("customer_no", case)
    query = f"SELECT DISTINCT dc.{col} AS customer_no FROM dim_client dc"
    params = {}
    if search:
        query += f" WHERE dc.{col} ILIKE :search"
        params["search"] = f"%{search}%"
    query += f" ORDER BY dc.{col} LIMIT {int(limit)}"
    return read_sql(query, params=params)


@st.cache_data(ttl=600, show_spinner=False)
def get_kpis():
    """KPIs de synthèse pour la page d'accueil (cf. 02_data_warehouse/kpis.md)."""
    case = detect_column_case()
    f = lambda c: f"f.{_q(c, case)}"
    query = f"""
    SELECT
        COUNT(DISTINCT f.{_q('customer_no', case)})                      AS nb_clients,
        COUNT(DISTINCT f.{_q('account_no', case)})                       AS nb_comptes,
        AVG({f('churn')}::float)                                         AS taux_churn_compte,
        AVG({f('acct_balance')})                                         AS solde_moyen_global,
        SUM(CASE WHEN {f('churn')} = 1 THEN 1 ELSE 0 END)                AS nb_comptes_clotures
    FROM fact_compte_client f
    """
    df = read_sql(query)

    case2 = case
    dc = lambda c: f"dc.{_q(c, case2)}"
    full_churn_query = f"""
    SELECT AVG({_q('client_full_churn', case)}::float) AS taux_churn_client
    FROM (
        SELECT DISTINCT f.{_q('customer_no', case)}, f.{_q('client_full_churn', case)}
        FROM fact_compte_client f
    ) t
    """
    df_full = read_sql(full_churn_query)
    df["taux_churn_client"] = df_full["taux_churn_client"].iloc[0]
    return df.iloc[0]


@st.cache_data(ttl=600, show_spinner=False)
def get_churn_by_segment(segment_col: str = "secteur_principal", top_n: int = 12):
    """Taux de churn agrégé par segment (secteur, branche, statut...) pour la
    page 'Analyse du churn' — équivalent web du KPI 1.3 de kpis.md."""
    df = get_client_dataset()
    g = (
        df.groupby(segment_col)
        .agg(taux_churn=("churn", "mean"), n_clients=("churn", "size"))
        .reset_index()
        .sort_values("n_clients", ascending=False)
        .head(top_n)
    )
    return g
