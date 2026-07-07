"""
app.py
------
Point d'entrée Streamlit. Page d'accueil = KPIs de synthèse, équivalent web
de la page Power BI "Vue d'ensemble" attendue dans 03_power_bi/ (taux de
churn global, volumétrie du portefeuille).

Lancement local :
    streamlit run app.py

Déploiement : voir DEPLOY.md.
"""

import streamlit as st
import pandas as pd

from utils.db import check_connection
from utils.queries import get_kpis, get_client_dataset
from utils.model import model_available

st.set_page_config(
    page_title="Churn Client — Vue d'ensemble",
    page_icon="📊",
    layout="wide",
)

st.title("📊 Prédiction du churn client — Tableau de bord")
st.caption(
    "Application de démonstration branchée en direct sur l'entrepôt PostgreSQL "
    "`churn_dw` (voir `01_etl/` et `02_data_warehouse/`) et sur le modèle final "
    "entraîné dans `04_machine_learning/` (XGBoost, PR-AUC 0.983)."
)

# --- Vérification de l'état du système (base + modèle) ----------------------
ok, msg = check_connection()
col_status1, col_status2 = st.columns(2)
with col_status1:
    if ok:
        st.success(f"🟢 Entrepôt PostgreSQL : {msg}")
    else:
        st.error(f"🔴 Entrepôt PostgreSQL : {msg}")
with col_status2:
    if model_available():
        st.success("🟢 Modèle de churn chargé")
    else:
        st.error("🔴 Modèle introuvable — voir DEPLOY.md")

if not ok:
    st.warning(
        "Impossible de charger les KPIs sans connexion à l'entrepôt. "
        "Vérifiez la configuration (variables d'environnement ou secrets Streamlit)."
    )
    st.stop()

st.divider()

# --- KPIs principaux ----------------------------------------------------
kpis = get_kpis()

st.subheader("Indicateurs clés")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Clients", f"{int(kpis['nb_clients']):,}".replace(",", " "))
c2.metric("Comptes", f"{int(kpis['nb_comptes']):,}".replace(",", " "))
c3.metric("Taux de churn (comptes)", f"{kpis['taux_churn_compte']*100:.1f} %")
c4.metric("Taux de churn (clients, full churn)", f"{kpis['taux_churn_client']*100:.1f} %")

c5, c6 = st.columns(2)
c5.metric("Solde moyen par compte", f"{kpis['solde_moyen_global']:,.0f}".replace(",", " ") + " (devise locale)")
c6.metric("Comptes clôturés", f"{int(kpis['nb_comptes_clotures']):,}".replace(",", " "))

st.caption(
    "Définitions : *churn (comptes)* = proportion de lignes compte-produit "
    "clôturées. *Churn client (full churn)* = proportion de clients dont "
    "**tous** les comptes sont clôturés — c'est la cible du modèle ML "
    "(voir `02_data_warehouse/kpis.md` §1.1-1.2)."
)

st.divider()

# --- Répartition rapide -------------------------------------------------
st.subheader("Répartition du portefeuille")
df = get_client_dataset()

col_a, col_b = st.columns(2)
with col_a:
    st.caption("Répartition churn / actif (niveau client)")
    churn_counts = df["churn"].value_counts().rename({0: "Actif", 1: "Churné"})
    st.bar_chart(churn_counts)
with col_b:
    st.caption("Top secteurs d'activité (nombre de clients)")
    top_sectors = df["secteur_principal"].value_counts().head(10)
    st.bar_chart(top_sectors)

st.divider()
st.page_link("pages/1_Analyse_du_churn.py", label="➡️ Voir l'analyse détaillée du churn", icon="📈")
st.page_link("pages/2_Comptes_a_risque.py", label="➡️ Voir la liste des comptes à risque + prédiction individuelle", icon="⚠️")
