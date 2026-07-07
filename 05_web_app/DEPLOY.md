# DEPLOY.md — Déploiement sur Streamlit Community Cloud

## ⚠️ Point critique à comprendre avant de déployer

Cette application se connecte à PostgreSQL **en direct** (pas de CSV embarqué).
Streamlit Community Cloud exécute votre app sur un serveur distant — **il ne
peut pas atteindre un PostgreSQL qui tourne sur `localhost` de votre PC**.
Il vous faut donc un PostgreSQL **accessible publiquement sur Internet**
avant de déployer.

Deux options, de la plus simple à la plus proche de votre setup ETL actuel :

| Option | Effort | Recommandé pour |
|---|---|---|
| **A. Hébergeur Postgres gratuit** (Neon, Supabase, Railway) | Faible | Démo / soutenance — **recommandé** |
| **B. Exposer votre Postgres local** (ngrok, port forwarding) | Moyen, fragile | Dépannage ponctuel uniquement |

Ce guide détaille l'option A avec **Neon** (offre gratuite généreuse, pas de
carte bancaire requise), mais la procédure est quasi identique avec Supabase
ou Railway.

---

## Étape 1 — Créer un PostgreSQL public gratuit (Neon)

1. Aller sur [neon.tech](https://neon.tech), créer un compte gratuit.
2. Créer un nouveau projet → une base nommée `churn_dw` est créée automatiquement
   (ou renommez-la).
3. Neon vous donne une chaîne de connexion du type :
   ```
   postgresql://<user>:<password>@<host>.neon.tech/churn_dw?sslmode=require
   ```
   Notez séparément `host`, `user`, `password`, `dbname` — vous en aurez besoin
   à l'étape 3.

## Étape 2 — Peupler ce Postgres distant avec vos données

Depuis votre machine locale, adaptez temporairement vos variables
d'environnement pour pointer vers Neon au lieu de `localhost`, puis relancez
le pipeline ETL :

```bash
export PGHOST=<host>.neon.tech
export PGPORT=5432
export PGDATABASE=churn_dw
export PGUSER=<user>
export PGPASSWORD=<password>

cd 01_etl
python pipeline.py
```

⏱️ Ça prend plus longtemps qu'en local (réseau), comptez plusieurs minutes
sur les 490k lignes de `fact_compte_client`.

Vérifiez ensuite que `04_machine_learning` fonctionne bien contre cette base
distante (mêmes variables d'environnement) :
```bash
cd 04_machine_learning/src
python db.py
```
Doit afficher `Connexion OK ... 7 tables trouvées.`

## Étape 3 — Préparer le modèle pour le déploiement

Streamlit Community Cloud déploie **uniquement le contenu de votre repo
GitHub**. Le fichier `04_machine_learning/models/model_final.joblib` est
exclu par `.gitignore` (`*.joblib`) — il faut donc le rendre disponible
autrement pour l'app déployée. Deux solutions :

### Solution recommandée : copier le modèle dans `05_web_app/assets/`
```bash
cp 04_machine_learning/models/model_final.joblib 05_web_app/assets/model_final.joblib
```
Puis, exceptionnellement, forcer son ajout au repo malgré le `.gitignore`
(le fichier fait ~1 Mo, largement sous la limite GitHub) :
```bash
git add -f 05_web_app/assets/model_final.joblib
git commit -m "05_web_app: inclure le modèle final pour le déploiement"
git push origin main
```
`utils/model.py` cherche automatiquement dans `05_web_app/assets/` si le
chemin `04_machine_learning/models/` n'est pas trouvé — aucune modification
de code nécessaire.

⚠️ Si le modèle change après un ré-entraînement, pensez à refaire cette copie.

## Étape 4 — Déployer sur Streamlit Community Cloud

1. Poussez votre repo sur GitHub (public ou privé, Streamlit Cloud gère les deux
   si vous connectez votre compte GitHub).
2. Aller sur [share.streamlit.io](https://share.streamlit.io), se connecter avec GitHub.
3. **New app** → sélectionner votre repo, la branche `main`, et le fichier
   principal : `05_web_app/app.py`.
4. Dans **Advanced settings → Secrets**, coller (en adaptant à vos vraies valeurs Neon) :
   ```toml
   PGHOST = "<host>.neon.tech"
   PGPORT = "5432"
   PGDATABASE = "churn_dw"
   PGUSER = "<user>"
   PGPASSWORD = "<password>"
   ```
5. **Deploy**. Premier déploiement : quelques minutes (installation des
   dépendances, dont xgboost).

## Étape 5 — Vérifier et documenter l'URL

Une fois déployée, l'app est accessible à une URL du type
`https://<nom-app>.streamlit.app`. Testez les 3 pages (accueil, analyse du
churn, comptes à risque + prédiction individuelle).

**N'oubliez pas** : ajoutez cette URL dans le `README.md` principal du projet
(à la racine du repo), comme demandé dans les livrables finaux.

---

## Dépannage

### `ModuleNotFoundError` au démarrage de l'app déployée
Vérifiez que `requirements.txt` est bien à la racine de `05_web_app/` (et non
à la racine du repo) — Streamlit Cloud cherche `requirements.txt` dans le
même dossier que le fichier principal indiqué au déploiement.

### `model_final.joblib introuvable`
Vérifiez l'étape 3 : le fichier doit être présent dans
`05_web_app/assets/model_final.joblib` **et committé** (pas juste présent en
local — `.gitignore` l'exclut par défaut, d'où le `git add -f`).

### Erreur au chargement du modèle (`AttributeError`, `ValueError` incompréhensible)
Presque toujours une incompatibilité de version entre l'environnement
d'entraînement et l'environnement de déploiement. Vérifiez que
`requirements.txt` épingle bien les mêmes versions de `scikit-learn` et
`xgboost` que celles utilisées lors de l'entraînement (voir commentaire dans
`requirements.txt`).

### `UndefinedColumn` en base
Même cause que dans `04_machine_learning` : la casse des colonnes en base
(minuscules vs `"MAJUSCULES"` quotées). `utils/queries.py::detect_column_case()`
gère les deux cas automatiquement — si l'erreur persiste, vérifiez que
`PGDATABASE` pointe bien vers la base fraîchement peuplée à l'étape 2, et pas
vers une ancienne base.

### L'app est très lente au premier chargement
Normal : `get_client_dataset()` charge les 363k clients en mémoire et
`predict_batch()` calcule un score pour chacun. Les résultats sont mis en
cache 10 minutes (`@st.cache_data(ttl=600)`) — les chargements suivants sont
quasi instantanés. Pour une démo fluide, envisagez de réduire ce périmètre
(ex. limiter à un échantillon) si la latence gêne la présentation.
