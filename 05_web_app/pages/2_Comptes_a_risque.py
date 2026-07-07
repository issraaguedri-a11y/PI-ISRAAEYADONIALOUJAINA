"""
2_Comptes_a_risque.py
-----------------------
Couvre les fonctionnalités minimales attendues du README d'origine :
1. Prédiction individuelle (formulaire).
2. Liste des comptes à risque (prédiction en lot sur les clients actifs).

Équivalent web de la page Power BI "Segmentation client" (profils, comptes
à risque).
"""

import streamlit as st
import pandas as pd

from utils.queries import get_client_dataset, get_client_by_id, list_customer_ids
from utils.model import predict_one, predict_batch, model_available, ALL_FEATURES

st.set_page_config(page_title="Comptes à risque", page_icon="⚠️", layout="wide")
st.title("⚠️ Prédiction du churn : individuelle & comptes à risque")

if not model_available():
    st.error("Modèle introuvable. Voir DEPLOY.md pour le déployer correctement.")
    st.stop()

tab1, tab2 = st.tabs(["🔍 Prédiction individuelle", "📋 Liste des comptes à risque"])

# ============================================================================
# TAB 1 — Prédiction individuelle
# ============================================================================
with tab1:
    st.subheader("Prédire le risque de churn d'un client")

    mode = st.radio(
        "Mode de saisie",
        ["Rechercher un client existant (CUSTOMER_NO)", "Saisir un profil manuellement"],
        horizontal=True,
    )

    features = None

    if mode.startswith("Rechercher"):
        search = st.text_input("Rechercher un CUSTOMER_NO (ex: C000123)", "")
        matches = list_customer_ids(search, limit=50) if search else pd.DataFrame()
        if not matches.empty:
            chosen = st.selectbox("Sélectionner le client", matches["customer_no"])
            if chosen:
                row = get_client_by_id(chosen)
                if row.empty:
                    st.warning("Aucune donnée trouvée pour ce client.")
                else:
                    features = row.iloc[0].to_dict()
                    with st.expander("Voir le profil complet récupéré depuis l'entrepôt"):
                        st.dataframe(row.T, use_container_width=True)
        elif search:
            st.info("Aucun client trouvé pour cette recherche.")

    else:
        st.caption(
            "Renseignez le profil du client. Les champs sont regroupés comme "
            "dans l'analyse du modèle (voir `04_machine_learning/comparison.md`)."
        )
        with st.form("manual_form"):
            st.markdown("**Profil socio-démographique**")
            c1, c2, c3 = st.columns(3)
            age = c1.number_input("Âge", min_value=18, max_value=100, value=45)
            nationality = c2.text_input("Nationalité (code)", "TN")
            residence = c3.text_input("Résidence (code)", "TN")
            c4, c5, c6 = st.columns(3)
            marital_status = c4.selectbox("Statut marital", ["C", "M", "D", "V", "Non applicable"])
            nature_client = c5.selectbox("Nature client", ["PPH", "PM", "PRO"])
            partyclass = c6.selectbox("Classification", ["Retail", "Corporate", "Corporate Small", "Elite"])
            c7, c8, c9 = st.columns(3)
            lob = c7.text_input("Ligne métier (LOB)", "4")
            score_kyc = c8.selectbox("Score KYC", ["LR", "MR", "H1", "H2", "H3"])
            completed_file = c9.selectbox("Dossier complet", ["YES", "Non"])

            st.markdown("**Comportement bancaire**")
            c10, c11, c12 = st.columns(3)
            nb_comptes = c10.number_input("Nombre de comptes", min_value=0, value=2)
            nb_produits_distincts = c11.number_input("Nombre de produits distincts", min_value=0, value=1)
            nb_secteurs = c12.number_input("Nombre de secteurs liés", min_value=0, value=1)
            c13, c14 = st.columns(2)
            nb_agences = c13.number_input("Nombre d'agences", min_value=0, value=1)
            secteur_principal = c14.text_input("Secteur d'activité principal", "Autre")

            st.markdown("**Ancienneté**")
            c15, c16, c17 = st.columns(3)
            anciennete_client_annees = c15.number_input("Ancienneté client (années)", min_value=0.0, value=5.0)
            anciennete_compte_moy_annees = c16.number_input("Ancienneté moyenne des comptes (années)", min_value=0.0, value=3.0)
            anciennete_compte_max_annees = c17.number_input("Ancienneté du plus vieux compte (années)", min_value=0.0, value=3.0)
            jours_depuis_derniere_revue_moy = st.number_input("Jours depuis la dernière revue KYC", min_value=0, value=365)

            st.markdown("**Finances**")
            c18, c19, c20 = st.columns(3)
            solde_total = c18.number_input("Solde total", value=1000.0)
            solde_moyen = c19.number_input("Solde moyen", value=500.0)
            salaire_moyen = c20.number_input("Salaire moyen déclaré", value=400.0)
            c21, c22 = st.columns(2)
            montant_total = c21.number_input("Montant total des produits", value=0.0)
            taux_fixe_moyen = c22.number_input("Taux fixe moyen", value=0.0)

            st.markdown("**Produits détenus**")
            c23, c24, c25, c26 = st.columns(4)
            a_credit = int(c23.checkbox("Crédit"))
            a_epargne_placement = int(c24.checkbox("Épargne / placement"))
            a_compte_courant = int(c25.checkbox("Compte courant", value=True))
            a_coffre = int(c26.checkbox("Coffre"))
            flag_incoherence_cloture = int(st.checkbox("Incohérence de clôture détectée (avancé)", value=False))

            submitted = st.form_submit_button("Calculer le score de risque", type="primary")

        if submitted:
            features = {
                "age": age, "nationality": nationality, "residence": residence,
                "marital_status": marital_status, "nature_client": nature_client,
                "partyclass": partyclass, "lob": lob, "score_kyc": score_kyc,
                "completed_file": completed_file,
                "nb_comptes": nb_comptes, "nb_produits_distincts": nb_produits_distincts,
                "nb_secteurs": nb_secteurs, "nb_agences": nb_agences,
                "secteur_principal": secteur_principal,
                "anciennete_client_annees": anciennete_client_annees,
                "anciennete_compte_moy_annees": anciennete_compte_moy_annees,
                "anciennete_compte_max_annees": anciennete_compte_max_annees,
                "jours_depuis_derniere_revue_moy": jours_depuis_derniere_revue_moy,
                "solde_total": solde_total, "solde_moyen": solde_moyen,
                "salaire_moyen": salaire_moyen, "montant_total": montant_total,
                "taux_fixe_moyen": taux_fixe_moyen,
                "a_credit": a_credit, "a_epargne_placement": a_epargne_placement,
                "a_compte_courant": a_compte_courant, "a_coffre": a_coffre,
                "flag_incoherence_cloture": flag_incoherence_cloture,
            }

    if features:
        pred, proba = predict_one(features)
        st.divider()
        col_res1, col_res2 = st.columns([1, 2])
        with col_res1:
            if pred == 1:
                st.error(f"### 🔴 Risque de churn élevé\n**Score : {proba:.1%}**")
            else:
                st.success(f"### 🟢 Risque de churn faible\n**Score : {proba:.1%}**")
        with col_res2:
            st.progress(proba, text=f"Probabilité de churn : {proba:.1%}")
            st.caption(
                "Score produit par le pipeline complet (préprocessing + XGBoost) "
                "entraîné dans `04_machine_learning/`. Seuil de décision : 50%."
            )

# ============================================================================
# TAB 2 — Liste des comptes à risque (prédiction en lot)
# ============================================================================
with tab2:
    st.subheader("Clients actifs les plus à risque")
    st.caption(
        "Prédiction en lot sur les clients dont le statut connu n'est pas "
        "déjà 'Closed'. Utile pour prioriser des actions de rétention."
    )

    df = get_client_dataset()
    active_df = df[df["dernier_statut_connu"] != "Closed"].copy() if "dernier_statut_connu" in df.columns else df.copy()

    with st.spinner("Calcul des scores de risque sur le portefeuille..."):
        scored = predict_batch(active_df)

    col_f1, col_f2, col_f3 = st.columns(3)
    seuil = col_f1.slider("Seuil de score minimum", 0.0, 1.0, 0.5, 0.05)
    secteur_filter = col_f2.multiselect("Filtrer par secteur", sorted(scored["secteur_principal"].dropna().unique()))
    top_n = col_f3.number_input("Nombre de clients à afficher", min_value=10, max_value=1000, value=100, step=10)

    filtered = scored[scored["score_risque"] >= seuil]
    if secteur_filter:
        filtered = filtered[filtered["secteur_principal"].isin(secteur_filter)]
    filtered = filtered.sort_values("score_risque", ascending=False).head(int(top_n))

    st.metric("Clients au-dessus du seuil", f"{len(filtered):,}".replace(",", " "))

    display_cols = [
        "customer_no", "score_risque", "age", "secteur_principal",
        "anciennete_client_annees", "solde_total", "nb_comptes",
    ]
    display_cols = [c for c in display_cols if c in filtered.columns]
    st.dataframe(
        filtered[display_cols].style.format({
            "score_risque": "{:.1%}",
            "anciennete_client_annees": "{:.1f}",
            "solde_total": "{:,.0f}",
        }),
        hide_index=True, use_container_width=True, height=500,
    )

    csv = filtered[display_cols].to_csv(index=False).encode("utf-8")
    st.download_button(
        "📥 Télécharger la liste (CSV)", csv,
        file_name="comptes_a_risque.csv", mime="text/csv",
    )
