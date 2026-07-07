"""
train.py
--------
Entraînement et comparaison de modèles de prédiction du churn client.

Modèles comparés : Régression logistique, KNN, Arbre de décision,
Random Forest, SVM, XGBoost.

Le jeu de données d'entrée (`data/client_churn_dataset.csv`) est produit par
`prepare_data.py`, qui l'obtient par requête SQL directe sur l'entrepôt
PostgreSQL `churn_dw` (voir ce module pour le détail des features).

Usage:
    python src/train.py                # entraîne les 6 modèles + sélection finale
    python src/train.py XGBoost         # entraîne un seul modèle
    python src/train.py finalize        # sélectionne le meilleur modèle déjà entraîné
"""
from __future__ import annotations

import time
import json
from pathlib import Path

import numpy as np
import pandas as pd
import joblib

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.neighbors import KNeighborsClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.svm import SVC
from xgboost import XGBClassifier
from sklearn.metrics import (
    precision_score, recall_score, f1_score, roc_auc_score,
    average_precision_score, confusion_matrix, classification_report,
)

RANDOM_STATE = 42

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

NUMERIC_FEATURES = [
    # NB : nb_comptes_clos est volontairement EXCLU. churn (= CLIENT_FULL_CHURN)
    # est défini par nb_comptes_clos == nb_comptes (cf. 01_etl/src/transform.py
    # ::add_features) : la conserver comme feature est une fuite de donnée
    # directe (le modèle atteint 100% en s'en servant, ce qui n'a aucune valeur
    # prédictive réelle -> constaté et corrigé lors du premier essai d'entraînement).
    "nb_comptes", "nb_produits_distincts",
    "anciennete_client_annees", "anciennete_compte_moy_annees", "anciennete_compte_max_annees",
    "jours_depuis_derniere_revue_moy",
    "solde_total", "solde_moyen", "salaire_moyen", "montant_total", "taux_fixe_moyen",
    # NB : nb_devises est volontairement EXCLU malgré son fort pouvoir prédictif
    # apparent. Investigation : nb_devises = 0 coïncide avec churn = 1 dans
    # ~100% des cas pour un sous-groupe de 139k clients (38% du dataset), car
    # CURRENCY n'est renseignée que lorsque les données produit sont complètes
    # côté SI source -- ce qui coïncide structurellement avec la clôture,
    # plutôt que de refléter un vrai comportement de multi-devise. Un test de
    # sensibilité (XGBoost sans cette variable) donne un PR-AUC quasi identique
    # (0.9828 vs 0.983), avec a_epargne_placement et montant_total qui prennent
    # le relais -- signal bien plus défendable et actionnable. Voir comparison.md.
    "nb_secteurs", "nb_agences",
    "a_credit", "a_epargne_placement", "a_compte_courant", "a_coffre",
    "flag_incoherence_cloture", "age",
]
CATEGORICAL_FEATURES = [
    "nationality", "residence", "marital_status", "nature_client",
    "partyclass", "lob", "score_kyc", "completed_file", "secteur_principal",
]
TARGET = "churn"


def load_dataset(path: Path = DATA_DIR / "client_churn_dataset.csv") -> pd.DataFrame:
    df = pd.read_csv(path)
    df["lob"] = df["lob"].astype(str)  # code numérique mais nominal, pas ordinal
    return df


def build_preprocessor() -> ColumnTransformer:
    numeric_pipe = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])
    categorical_pipe = Pipeline([
        ("imputer", SimpleImputer(strategy="constant", fill_value="Inconnu")),
        ("ohe", OneHotEncoder(handle_unknown="ignore")),
    ])
    return ColumnTransformer([
        ("num", numeric_pipe, NUMERIC_FEATURES),
        ("cat", categorical_pipe, CATEGORICAL_FEATURES),
    ])


def get_models() -> dict:
    return {
        "Regression_logistique": LogisticRegression(
            max_iter=1000, class_weight="balanced", random_state=RANDOM_STATE
        ),
        "KNN": KNeighborsClassifier(n_neighbors=25, n_jobs=-1),
        "Arbre_de_decision": DecisionTreeClassifier(
            max_depth=8, class_weight="balanced", random_state=RANDOM_STATE
        ),
        "Random_Forest": RandomForestClassifier(
            n_estimators=300, max_depth=12, n_jobs=-1,
            class_weight="balanced", random_state=RANDOM_STATE
        ),
        "SVM": SVC(
            kernel="rbf", probability=True, class_weight="balanced", random_state=RANDOM_STATE
        ),
        "XGBoost": XGBClassifier(
            n_estimators=300, max_depth=6, learning_rate=0.1,
            eval_metric="logloss", n_jobs=-1, random_state=RANDOM_STATE
        ),
    }


# KNN et SVM ne passent pas à l'échelle sur ~290k lignes d'entraînement :
# - KNN : coût de PRÉDICTION en O(n_test x n_train) sans structure d'indexation adaptée
#   à un mélange dense (one-hot) + creux à si haute dimension.
# - SVM (noyau RBF) : complexité d'ENTRAÎNEMENT quadratique à cubique en n_train.
# Ils sont donc entraînés sur un sous-échantillon stratifié, ce qui est indiqué
# explicitement dans le tableau comparatif (colonne n_entrainement).
SAMPLE_SIZES = {"SVM": 8000, "KNN": 40000}


def evaluate(y_true, y_pred, y_proba) -> dict:
    return {
        "precision": round(precision_score(y_true, y_pred), 4),
        "recall": round(recall_score(y_true, y_pred), 4),
        "f1": round(f1_score(y_true, y_pred), 4),
        "roc_auc": round(roc_auc_score(y_true, y_proba), 4),
        "pr_auc": round(average_precision_score(y_true, y_proba), 4),
    }


def get_split(df: pd.DataFrame):
    X = df[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
    y = df[TARGET]
    return train_test_split(X, y, test_size=0.2, stratify=y, random_state=RANDOM_STATE)


def train_one(name: str) -> dict:
    """Entraîne et évalue un seul modèle ; ajoute son résultat à results.json."""
    df = load_dataset()
    X_train, X_test, y_train, y_test = get_split(df)

    preprocessor = build_preprocessor()
    model = get_models()[name]
    pipe = Pipeline([("prep", preprocessor), ("model", model)])

    t0 = time.time()
    sample_size = SAMPLE_SIZES.get(name)
    if sample_size and len(X_train) > sample_size:
        X_tr, _, y_tr, _ = train_test_split(
            X_train, y_train, train_size=sample_size, stratify=y_train, random_state=RANDOM_STATE
        )
    else:
        X_tr, y_tr = X_train, y_train

    pipe.fit(X_tr, y_tr)

    if name == "KNN":
        X_test_eval, _, y_test_eval, _ = train_test_split(
            X_test, y_test, train_size=15000, stratify=y_test, random_state=RANDOM_STATE
        )
    else:
        X_test_eval, y_test_eval = X_test, y_test

    y_pred = pipe.predict(X_test_eval)
    y_proba = pipe.predict_proba(X_test_eval)[:, 1]

    metrics = evaluate(y_test_eval, y_pred, y_proba)
    metrics["temps_entrainement_s"] = round(time.time() - t0, 1)
    metrics["n_entrainement"] = len(X_tr)
    metrics["n_evaluation"] = len(X_test_eval)
    print(name, metrics)

    results_path = DATA_DIR / "results.json"
    try:
        with open(results_path) as f:
            results = json.load(f)
    except FileNotFoundError:
        results = {}
    results[name] = metrics
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)

    joblib.dump(pipe, MODELS_DIR / f"{name}.joblib")

    cm = confusion_matrix(y_test_eval, y_pred)
    np.savetxt(DATA_DIR / f"{name}_confusion_matrix.csv", cm, delimiter=",", fmt="%d")
    with open(DATA_DIR / f"{name}_classification_report.txt", "w") as f:
        f.write(classification_report(y_test_eval, y_pred))

    return metrics


def finalize():
    """À appeler après l'entraînement de tous les modèles : sélectionne le meilleur (PR-AUC)."""
    with open(DATA_DIR / "results.json") as f:
        results = json.load(f)
    results_df = pd.DataFrame(results).T
    results_df.to_csv(DATA_DIR / "model_comparison.csv")

    best_name = results_df["pr_auc"].astype(float).idxmax()
    print("Meilleur modèle (PR-AUC):", best_name)

    with open(DATA_DIR / "best_model.json", "w") as f:
        json.dump({"best_model": best_name, "metrics": results[best_name]}, f, indent=2)

    import shutil, os
    shutil.copy(MODELS_DIR / f"{best_name}.joblib", MODELS_DIR / "model_final.joblib")
    for name in results:
        if name != best_name:
            p = MODELS_DIR / f"{name}.joblib"
            if p.exists():
                os.remove(p)
    return results_df, best_name


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "finalize":
        finalize()
    elif len(sys.argv) > 1:
        train_one(sys.argv[1])
    else:
        for m in get_models():
            train_one(m)
        finalize()
