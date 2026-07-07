# 04_machine_learning — Modélisation prédictive du churn

Ce dossier contient l'ensemble du travail de modélisation du churn client :
préparation des données **par requête SQL sur l'entrepôt PostgreSQL**,
entraînement, comparaison de 6 modèles, et analyse d'interprétabilité.

## Changement important par rapport à une v1

Une première version de ce dossier lisait des fichiers CSV bruts sans en-tête
(faute d'accès au data warehouse à l'époque). **Cette version lit directement
l'entrepôt PostgreSQL `churn_dw`** construit par `01_etl/` et documenté dans
`02_data_warehouse/` — plus de dépendance à des CSV intermédiaires. Les vrais
noms de colonnes du schéma en étoile sont utilisés partout
(`fact_compte_client`, `dim_client`, `dim_industry`, etc., cf.
`02_data_warehouse/schema/create_tables.sql`).

⚠️ Selon la façon dont votre entrepôt a été chargé, les colonnes peuvent
exister en base soit en minuscules (`client_sk`) soit en **MAJUSCULES
quotées** (`"CLIENT_SK"`). `src/prepare_data.py` détecte automatiquement la
casse au démarrage (`detect_column_case()`) — vous n'avez rien à faire à ce
sujet, mais si vous voyez le message `UndefinedColumn` malgré tout, voir la
section [Dépannage](#dépannage-erreurs-fréquentes) ci-dessous.

---

## 🚀 Étapes d'exécution (pas à pas)

Le dossier `data/` (jeux de données dérivés, résultats, graphiques) et
`models/` (modèle final) sont **entièrement régénérables** — vous pouvez les
vider et relancer le pipeline à tout moment sans perte, à condition que
l'entrepôt PostgreSQL soit peuplé.

### Étape 0 — Prérequis (une seule fois)

1. **PostgreSQL doit tourner** et l'entrepôt `churn_dw` doit être peuplé.
   Si ce n'est pas déjà fait, exécuter le pipeline ETL depuis la racine du projet :
   ```bash
   cd 01_etl
   python pipeline.py
   ```
   (voir `01_etl/README.md` et `02_data_warehouse/README.md` si besoin).

2. **Variables de connexion** à définir dans votre terminal (ou un fichier `.env`) :
   ```
   PGHOST=localhost
   PGPORT=5432
   PGDATABASE=churn_dw
   PGUSER=postgres
   PGPASSWORD=postgres
   ```

3. **Dépendances Python** :
   ```bash
   pip install pandas numpy scikit-learn xgboost shap matplotlib joblib sqlalchemy psycopg2-binary
   ```

4. **Vérifier la connexion** avant d'aller plus loin :
   ```bash
   cd 04_machine_learning/src
   python db.py
   ```
   Doit afficher : `[db] Connexion OK à 'churn_dw' sur localhost:5432 — 7 tables trouvées.`
   Si ça échoue, voir [Dépannage](#dépannage-erreurs-fréquentes).

### Étape 1 — Préparation des données

Construit `data/client_churn_dataset.csv` (363 569 clients, 1 ligne = 1 client)
par requête SQL sur l'entrepôt.

**Option A — notebook** (recommandé pour voir les résultats intermédiaires) :
Ouvrir `notebooks/01_preparation.ipynb`, cliquer **Restart** puis **Run All**.

**Option B — ligne de commande** (plus rapide) :
```bash
cd 04_machine_learning/src
python prepare_data.py
```

✅ Résultat attendu :
```
[prepare_data] 363,569 clients récupérés depuis l'entrepôt.
[prepare_data] Dataset sauvegardé : .../data/client_churn_dataset.csv  shape=(363569, 32)
churn
0    0.554973
1    0.445027
```

### Étape 2 — Entraînement des 6 modèles

Nécessite que l'étape 1 ait tourné (`data/client_churn_dataset.csv` doit exister).

**Option A — notebook** :
Ouvrir `notebooks/02_entrainement.ipynb`, **Restart** puis **Run All**.

**Option B — ligne de commande** :
```bash
cd 04_machine_learning/src
python train.py
```

⏱️ Compter **2-3 minutes** : les 6 modèles s'entraînent l'un après l'autre
(Régression logistique, Arbre de décision, KNN, Random Forest, SVM, XGBoost).
**Random Forest est le plus long** (~1-2 min) — ce n'est pas un blocage,
c'est normal.

Si vous préférez entraîner un modèle à la fois (utile pour déboguer) :
```bash
python train.py Regression_logistique
python train.py Arbre_de_decision
python train.py KNN
python train.py SVM
python train.py XGBoost
python train.py Random_Forest
python train.py finalize    # sélectionne le meilleur (PR-AUC) et sauvegarde models/model_final.joblib
```

✅ Résultat attendu : `models/model_final.joblib` créé, `data/model_comparison.csv`
et `data/results.json` remplis, meilleur modèle = **XGBoost** (PR-AUC ≈ 0.983).

### Étape 3 — Interprétabilité (feature importance + SHAP)

Nécessite que l'étape 2 ait tourné (`models/model_final.joblib` doit exister).

**Option A — notebook** :
Ouvrir `notebooks/03_evaluation.ipynb`, **Restart** puis **Run All**.

**Option B — ligne de commande** :
```bash
cd 04_machine_learning/src
python interpretability.py
```

✅ Résultat attendu : `data/feature_importance.png`, `data/shap_summary.png`,
`data/feature_importance.csv`, `data/shap_importance.csv` créés.

### Récapitulatif — tout enchaîner d'un coup

```bash
cd 04_machine_learning/src
python prepare_data.py
python train.py
python interpretability.py
```

---

## Ordre de dépendance entre les étapes

```
01_preparation.ipynb / prepare_data.py
        ↓ crée data/client_churn_dataset.csv
02_entrainement.ipynb / train.py
        ↓ crée models/*.joblib + data/results.json, model_comparison.csv, best_model.json,
        ↓ *_classification_report.txt, *_confusion_matrix.csv
03_evaluation.ipynb / interpretability.py
        ↓ crée data/feature_importance.*, data/shap_*.png, data/models_comparison.png
```

Chaque étape lit les fichiers produits par la précédente. Si vous videz
`data/` ou `models/`, il faut relancer les étapes concernées **dans l'ordre**.

---

## Dépannage (erreurs fréquentes)

### `UndefinedColumn: la colonne f.client_sk n'existe pas` (ou variante)

Deux causes possibles :

1. **Kernel Jupyter avec un import en cache.** Si vous avez déjà exécuté une
   cellule qui importe `prepare_data` plus tôt dans la session, Python garde
   l'ancienne version du module en mémoire même après avoir modifié le
   fichier sur le disque. **Solution : cliquer sur "Restart" (pas juste
   ré-exécuter la cellule), puis "Run All".**

2. **Casse des colonnes en base incohérente.** Vérifier avec :
   ```sql
   SELECT table_name, column_name FROM information_schema.columns
   WHERE table_name IN ('fact_compte_client', 'dim_client', 'dim_industry')
     AND column_name ILIKE '%sk%'
   ORDER BY table_name, column_name;
   ```
   Toutes les colonnes `_SK` doivent avoir la même casse partout. Si ce
   n'est pas le cas, contacter le mainteneur du script ETL — ce n'est pas
   censé arriver avec le pipeline standard.

### `connection to server at "localhost" ... Connection refused`

PostgreSQL n'est pas démarré. Sur Windows, vérifier le service PostgreSQL
dans les Services (`services.msc`) ou relancer via pgAdmin. Sur Linux :
```bash
sudo service postgresql start
```

### `python : Python est introuvable` (PowerShell, Windows)

L'alias Microsoft Store de `python` interfère. Utiliser :
```powershell
py prepare_data.py
```
ou le chemin complet vers votre installation :
```powershell
& "C:\Users\<vous>\AppData\Local\Programs\Python\Python3XX\python.exe" prepare_data.py
```

### `Tables manquantes dans 'churn_dw'`

Le pipeline ETL n'a pas (encore) peuplé l'entrepôt. Relancer
`python 01_etl/pipeline.py` depuis la racine du projet et vérifier qu'il
se termine sans erreur.

### Je veux repartir de zéro (vider `data/` et `models/`)

C'est sans danger : ces dossiers sont entièrement régénérés par les 3
étapes ci-dessus, à condition que l'entrepôt PostgreSQL (étape 0) soit
toujours peuplé. Il suffit de relancer les étapes 1 → 2 → 3 dans l'ordre.

---

## Structure

```
04_machine_learning/
├── notebooks/
│   ├── 01_preparation.ipynb    # requête SQL -> jeu de données client (grain = 1 client)
│   ├── 02_entrainement.ipynb   # entraînement des 6 modèles
│   └── 03_evaluation.ipynb     # comparaison, matrice de confusion, SHAP
├── src/
│   ├── db.py                   # connexion PostgreSQL (SQLAlchemy) + détection de casse
│   ├── prepare_data.py         # requête SQL d'agrégation compte -> client + features
│   ├── train.py                # préprocessing + entraînement + évaluation des 6 modèles
│   └── interpretability.py     # feature importance + SHAP sur le modèle final
├── models/
│   └── model_final.joblib      # pipeline complet (préprocessing + XGBoost) — régénérable
├── data/                        # tout ce dossier est régénérable, voir "Étapes" ci-dessus
│   ├── client_churn_dataset.csv
│   ├── model_comparison.csv
│   ├── best_model.json
│   ├── results.json
│   ├── feature_importance.csv / .png
│   ├── shap_importance.csv / shap_summary.png
│   └── *_classification_report.txt / *_confusion_matrix.csv (par modèle)
├── comparison.md                # tableau comparatif + fuites de données écartées + justification
└── README.md                    # ce fichier
```

## Contenu minimum — statut

- ✅ **Source de données** : requête SQL directe sur l'entrepôt PostgreSQL (pas de CSV brut).
- ✅ **6 modèles comparés** : Régression logistique, KNN, Arbre de décision, Random Forest, SVM, XGBoost.
- ✅ **Métriques adaptées au déséquilibre** : precision, recall, F1, ROC-AUC, PR-AUC (voir `comparison.md`).
- ✅ **Modèle final retenu** : XGBoost (PR-AUC 0.983), justifié dans `comparison.md`.
- ✅ **Interprétabilité** : importance des features (gain XGBoost) + SHAP.
- ✅ **Fuites de données investiguées et corrigées** : `nb_comptes_clos` (fuite directe) et
  `nb_devises` (fuite indirecte / artefact de complétude) — voir `comparison.md` pour le détail
  de l'investigation, avec test de sensibilité chiffré.

## Utiliser le modèle final

```python
import joblib
pipe = joblib.load("models/model_final.joblib")
pipe.predict(X_nouveaux_clients)
```

`X_nouveaux_clients` doit contenir les colonnes définies dans
`src/train.py::NUMERIC_FEATURES` et `CATEGORICAL_FEATURES` — le plus simple
est de repartir de `src/prepare_data.py::build_client_dataset()` pour
générer ces features de la même façon que pour l'entraînement.