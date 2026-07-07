"""
interpretability.py
--------------------
Analyse d'interprétabilité du modèle final (XGBoost) : importance des
features (gain) et valeurs SHAP sur un échantillon du jeu de test.

Usage:
    python src/interpretability.py
"""
from pathlib import Path
import json

import joblib
import numpy as np
import pandas as pd
import shap
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from train import load_dataset, get_split, NUMERIC_FEATURES, CATEGORICAL_FEATURES

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"

pipe = joblib.load(MODELS_DIR / "model_final.joblib")
df = load_dataset()
X_train, X_test, y_train, y_test = get_split(df)

preprocessor = pipe.named_steps["prep"]
model = pipe.named_steps["model"]

feature_names = (
    NUMERIC_FEATURES
    + list(preprocessor.named_transformers_["cat"].named_steps["ohe"].get_feature_names_out(CATEGORICAL_FEATURES))
)

# --- Feature importance (gain XGBoost) --------------------------------------
importances = model.feature_importances_
imp_df = pd.DataFrame({"feature": feature_names, "importance": importances})
imp_df = imp_df.sort_values("importance", ascending=False)
imp_df.to_csv(DATA_DIR / "feature_importance.csv", index=False)

plt.figure(figsize=(8, 6))
top = imp_df.head(15).iloc[::-1]
plt.barh(top["feature"], top["importance"])
plt.title("Importance des features (gain XGBoost) - Top 15")
plt.tight_layout()
plt.savefig(DATA_DIR / "feature_importance.png", dpi=120)
plt.close()

# --- SHAP ---------------------------------------------------------------
sample = X_test.sample(n=min(2000, len(X_test)), random_state=42)
X_sample_transformed = preprocessor.transform(sample)
if hasattr(X_sample_transformed, "toarray"):
    X_sample_transformed = X_sample_transformed.toarray()

explainer = shap.TreeExplainer(model)
shap_values = explainer.shap_values(X_sample_transformed)

shap_imp = pd.DataFrame({
    "feature": feature_names,
    "mean_abs_shap": np.abs(shap_values).mean(axis=0),
}).sort_values("mean_abs_shap", ascending=False)
shap_imp.to_csv(DATA_DIR / "shap_importance.csv", index=False)

plt.figure()
shap.summary_plot(
    shap_values, X_sample_transformed, feature_names=feature_names,
    show=False, max_display=15,
)
plt.tight_layout()
plt.savefig(DATA_DIR / "shap_summary.png", dpi=120, bbox_inches="tight")
plt.close()

print("Top 10 features (SHAP):")
print(shap_imp.head(10).to_string(index=False))
