"""
1_Analyse_du_churn.py
----------------------
Équivalent web de la page Power BI "Analyse du churn" attendue dans
03_power_bi/ : segmentation du taux de churn par âge, secteur, ancienneté,
produit (cf. 02_data_warehouse/kpis.md §1.3).
"""

import streamlit as st
import pandas as pd

from utils.queries import get_client_dataset

st.set_page_config(page_title="Analyse du churn", page_icon="📈", layout="wide")
st.title("📈 Analyse du churn par segment")

df = get_client_dataset()

st.caption(
    f"Analyse sur {len(df):,} clients — taux de churn global : "
    f"{df['churn'].mean()*100:.1f} %".replace(",", " ")
)

st.divider()

# --- Par tranche d'âge ---------------------------------------------------
st.subheader("Taux de churn par tranche d'âge")
df["tranche_age"] = pd.cut(
    df["age"], bins=[0, 25, 35, 45, 55, 65, 120],
    labels=["<25", "25-34", "35-44", "45-54", "55-64", "65+"],
)
by_age = df.groupby("tranche_age", observed=True)["churn"].agg(["mean", "size"]).reset_index()
by_age.columns = ["Tranche d'âge", "Taux de churn", "Nb clients"]
col1, col2 = st.columns([2, 1])
with col1:
    st.bar_chart(by_age.set_index("Tranche d'âge")["Taux de churn"])
with col2:
    st.dataframe(
        by_age.style.format({"Taux de churn": "{:.1%}", "Nb clients": "{:,.0f}"}),
        hide_index=True, use_container_width=True,
    )

st.divider()

# --- Par secteur d'activité ------------------------------------------------
st.subheader("Taux de churn par secteur d'activité")
by_sector = (
    df.groupby("secteur_principal")["churn"]
    .agg(["mean", "size"]).reset_index()
    .rename(columns={"secteur_principal": "Secteur", "mean": "Taux de churn", "size": "Nb clients"})
    .sort_values("Nb clients", ascending=False)
    .head(15)
)
col3, col4 = st.columns([2, 1])
with col3:
    st.bar_chart(by_sector.set_index("Secteur")["Taux de churn"])
with col4:
    st.dataframe(
        by_sector.style.format({"Taux de churn": "{:.1%}", "Nb clients": "{:,.0f}"}),
        hide_index=True, use_container_width=True,
    )

st.divider()

# --- Par ancienneté -------------------------------------------------------
st.subheader("Taux de churn par ancienneté client")
df["tranche_anciennete"] = pd.cut(
    df["anciennete_client_annees"],
    bins=[0, 2, 5, 10, 15, 20, 100],
    labels=["0-2 ans", "2-5 ans", "5-10 ans", "10-15 ans", "15-20 ans", "20+ ans"],
)
by_seniority = df.groupby("tranche_anciennete", observed=True)["churn"].agg(["mean", "size"]).reset_index()
by_seniority.columns = ["Ancienneté", "Taux de churn", "Nb clients"]
col5, col6 = st.columns([2, 1])
with col5:
    st.bar_chart(by_seniority.set_index("Ancienneté")["Taux de churn"])
with col6:
    st.dataframe(
        by_seniority.style.format({"Taux de churn": "{:.1%}", "Nb clients": "{:,.0f}"}),
        hide_index=True, use_container_width=True,
    )
st.caption(
    "⚠️ Une part importante des clients churnés n'a pas d'ancienneté de compte "
    "renseignée (voir `04_machine_learning/comparison.md`, section Limites connues) "
    "— à interpréter avec prudence."
)

st.divider()

# --- Par détention de produits ---------------------------------------------
st.subheader("Taux de churn selon les produits détenus")
product_flags = {
    "a_credit": "Détient un crédit",
    "a_epargne_placement": "Détient épargne/placement",
    "a_compte_courant": "Détient un compte courant",
    "a_coffre": "Détient un coffre",
}
rows = []
for col, label in product_flags.items():
    sub = df.groupby(col)["churn"].mean()
    rows.append({
        "Produit": label,
        "Taux de churn (sans)": sub.get(0, float("nan")),
        "Taux de churn (avec)": sub.get(1, float("nan")),
    })
prod_df = pd.DataFrame(rows)
st.dataframe(
    prod_df.style.format({"Taux de churn (sans)": "{:.1%}", "Taux de churn (avec)": "{:.1%}"}),
    hide_index=True, use_container_width=True,
)
st.caption(
    "La détention d'un produit épargne/placement ressort comme le facteur le "
    "plus protecteur — cohérent avec l'analyse SHAP du modèle "
    "(`04_machine_learning/data/shap_summary.png`)."
)
