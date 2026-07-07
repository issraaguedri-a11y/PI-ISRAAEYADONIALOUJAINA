"""
model.py
--------
Chargement du modèle final entraîné (`04_machine_learning/models/model_final.joblib`)
et fonctions d'inférence, individuelles ou en lot.

Le pipeline scikit-learn chargé inclut tout le préprocessing (imputation,
standardisation, one-hot encoding) — voir `04_machine_learning/src/train.py`
pour le détail de sa construction. Cette page ne fait qu'appeler `.predict()`
/ `.predict_proba()` dessus.
"""

from __future__ import annotations

from pathlib import Path
import joblib
import pandas as pd
import streamlit as st

# Emplacement du modèle : on suppose que 05_web_app est un sous-dossier du
# même repo que 04_machine_learning (structure standard du projet). Si vous
# déployez 05_web_app seul (repo séparé), copiez model_final.joblib dans
# 05_web_app/assets/ et ajustez MODEL_PATH ci-dessous.
_CANDIDATE_PATHS = [
    Path(__file__).resolve().parents[2] / "04_machine_learning" / "models" / "model_final.joblib",
    Path(__file__).resolve().parents[1] / "assets" / "model_final.joblib",
]

NUMERIC_FEATURES = [
    "nb_comptes", "nb_produits_distincts",
    "anciennete_client_annees", "anciennete_compte_moy_annees", "anciennete_compte_max_annees",
    "jours_depuis_derniere_revue_moy",
    "solde_total", "solde_moyen", "salaire_moyen", "montant_total", "taux_fixe_moyen",
    "nb_secteurs", "nb_agences",
    "a_credit", "a_epargne_placement", "a_compte_courant", "a_coffre",
    "flag_incoherence_cloture", "age",
]
CATEGORICAL_FEATURES = [
    "nationality", "residence", "marital_status", "nature_client",
    "partyclass", "lob", "score_kyc", "completed_file", "secteur_principal",
]
ALL_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES


@st.cache_resource(show_spinner="Chargement du modèle...")
def load_model():
    for path in _CANDIDATE_PATHS:
        if path.exists():
            return joblib.load(path)
    raise FileNotFoundError(
        "model_final.joblib introuvable. Emplacements testés :\n"
        + "\n".join(str(p) for p in _CANDIDATE_PATHS)
        + "\nVoir DEPLOY.md pour la marche à suivre."
    )


def model_available() -> bool:
    return any(p.exists() for p in _CANDIDATE_PATHS)


def predict_one(features: dict) -> tuple[int, float]:
    """Prédit le churn pour un client (dict de features) -> (classe, probabilité)."""
    pipe = load_model()
    row = {c: features.get(c) for c in ALL_FEATURES}
    df = pd.DataFrame([row])
    pred = int(pipe.predict(df)[0])
    proba = float(pipe.predict_proba(df)[0, 1])
    return pred, proba


def predict_batch(df: pd.DataFrame) -> pd.DataFrame:
    """Prédit le churn pour un DataFrame de clients (mêmes colonnes que
    ALL_FEATURES). Renvoie le DataFrame enrichi de `churn_predit` et `score_risque`."""
    pipe = load_model()
    missing = [c for c in ALL_FEATURES if c not in df.columns]
    if missing:
        raise ValueError(f"Colonnes manquantes pour la prédiction : {missing}")
    X = df[ALL_FEATURES]
    out = df.copy()
    out["churn_predit"] = pipe.predict(X)
    out["score_risque"] = pipe.predict_proba(X)[:, 1]
    return out
