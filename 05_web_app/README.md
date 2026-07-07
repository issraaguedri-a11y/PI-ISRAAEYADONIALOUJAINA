# 05 — Application Web

Application Streamlit de démonstration : prédiction du churn client,
branchée **en direct sur l'entrepôt PostgreSQL** `churn_dw` (même source que
`04_machine_learning/`) et sur le modèle final entraîné (XGBoost).

## Fonctionnalités

1. **Page d'accueil** (`app.py`) — KPIs de synthèse : taux de churn global
   (niveau compte et niveau client), volumétrie du portefeuille.
2. **Analyse du churn** (`pages/1_Analyse_du_churn.py`) — segmentation du
   taux de churn par âge, secteur d'activité, ancienneté, produits détenus.
3. **Comptes à risque** (`pages/2_Comptes_a_risque.py`) —
   - Prédiction individuelle (recherche d'un client existant par
     `CUSTOMER_NO`, ou saisie manuelle d'un profil).
   - Liste des comptes actifs les plus à risque (prédiction en lot),
     filtrable par seuil de score et par secteur, exportable en CSV.

Ces 3 pages couvrent volontairement les mêmes angles que les pages attendues
dans `03_power_bi/` (vue d'ensemble, analyse du churn, segmentation client) —
c'est une preuve de concept fonctionnelle, pas un remplacement de Power BI.

---

## 🚀 Exécution en local (pas à pas)

### Étape 0 — Prérequis

1. **L'entrepôt PostgreSQL `churn_dw` doit être peuplé** (voir
   `01_etl/README.md` et `04_machine_learning/README.md` si besoin).
2. **Le modèle final doit exister** :
   `04_machine_learning/models/model_final.joblib`. S'il n'existe pas encore,
   lancez d'abord l'entraînement :
   ```bash
   cd 04_machine_learning/src
   python prepare_data.py
   python train.py
   ```
3. **Variables de connexion** (mêmes conventions que partout ailleurs dans
   le projet) :
   ```bash
   export PGHOST=localhost
   export PGPORT=5432
   export PGDATABASE=churn_dw
   export PGUSER=postgres
   export PGPASSWORD=postgres
   ```
4. **Dépendances** :
   ```bash
   cd 05_web_app
   pip install -r requirements.txt
   ```

### Étape 1 — Lancer l'app

```bash
cd 05_web_app
streamlit run app.py
```

Le navigateur s'ouvre automatiquement sur `http://localhost:8501`. La page
d'accueil affiche un statut vert pour la base et le modèle si tout est en
ordre.

✅ Résultat attendu à l'accueil : ~363 569 clients, taux de churn client
~44,5 %, statuts "Entrepôt PostgreSQL" et "Modèle de churn chargé" tous deux
en vert.

---

## Déploiement public

Voir **[DEPLOY.md](./DEPLOY.md)** pour la procédure complète sur Streamlit
Community Cloud. Point important à lire avant de s'y lancer : contrairement
à l'exécution locale, un déploiement cloud ne peut pas atteindre un
PostgreSQL sur `localhost` — il faut un Postgres accessible publiquement
(Neon, Supabase, Railway...), voir DEPLOY.md pour la marche à suivre détaillée.

Une fois déployée, ajoutez l'URL publique dans le `README.md` principal du
projet (à la racine du repo).

---

## Dépannage

### `UndefinedColumn` en base
Même souci que `04_machine_learning` — les colonnes peuvent être en
minuscules ou en `"MAJUSCULES"` quotées selon la façon dont l'entrepôt a été
chargé. `utils/queries.py::detect_column_case()` s'adapte automatiquement ;
si l'erreur persiste, vérifiez que `PGDATABASE` pointe vers la bonne base.

### `model_final.joblib introuvable`
Le modèle n'a pas encore été entraîné, ou vous exécutez `05_web_app` en
dehors de la structure standard du repo (où il cherche
`../04_machine_learning/models/model_final.joblib` par rapport à
`05_web_app/`). Voir Étape 0.3 ci-dessus, ou copiez le fichier dans
`05_web_app/assets/` (utile aussi pour le déploiement, voir DEPLOY.md).

### `connection to server ... Connection refused`
PostgreSQL n'est pas démarré, ou les variables d'environnement ne sont pas
exportées dans le terminal qui lance `streamlit run`.

### L'app tourne mais les pages sont lentes au premier chargement
Normal, les requêtes sont mises en cache 10 minutes
(`@st.cache_data(ttl=600)`). Les chargements suivants sont rapides.

---

## Structure

```
05_web_app/
├── app.py                          # page d'accueil : KPIs de synthèse
├── pages/
│   ├── 1_Analyse_du_churn.py       # segmentation du churn (âge, secteur, ancienneté, produits)
│   └── 2_Comptes_a_risque.py       # prédiction individuelle + liste des comptes à risque
├── utils/
│   ├── db.py                       # connexion PostgreSQL (secrets Streamlit ou variables d'env)
│   ├── queries.py                  # requêtes SQL (détection auto de la casse des colonnes)
│   └── model.py                    # chargement du modèle final + prédiction individuelle/lot
├── assets/                         # (vide par défaut) copie du modèle pour le déploiement, voir DEPLOY.md
├── requirements.txt                # dépendances, versions épinglées pour compatibilité avec le modèle
├── DEPLOY.md                       # procédure de déploiement Streamlit Community Cloud
└── README.md                       # ce fichier
```

## Notes de conception

- **Pas de duplication de modèle** : l'app utilise directement
  `model_final.joblib` produit par `04_machine_learning/` — pas de
  réentraînement ni de logique de feature engineering dupliquée côté app
  (à part la requête SQL elle-même, dupliquée dans `utils/queries.py` pour
  que `05_web_app` reste déployable indépendamment de `04_machine_learning`,
  cf. commentaire dans ce fichier).
- **Mise en cache** : connexions (`st.cache_resource`) et résultats de
  requêtes (`st.cache_data`, TTL 10 min) pour limiter la charge sur
  l'entrepôt PostgreSQL lors de la démo.
- **Robustesse casse des colonnes** : reprend la même détection automatique
  que `04_machine_learning/src/prepare_data.py` (voir son README pour le
  contexte de cette contrainte).
