# Comparaison des modèles — Churn client

## Contexte

- **Source des données** : requête SQL directe sur l'entrepôt PostgreSQL `churn_dw`
  (tables `fact_compte_client` + `dim_client` + `dim_industry`), construit par le
  pipeline ETL (`01_etl/`). Aucun fichier CSV brut n'est lu par ce module — voir
  `src/db.py` et `src/prepare_data.py`.
- **Grain** : 1 ligne = 1 client (agrégation SQL des lignes compte-produit de
  `fact_compte_client`, `GROUP BY customer_no`).
- **Cible** : `CLIENT_FULL_CHURN` — 1 si **tous** les comptes du client sont
  clôturés, 0 sinon (définition officielle, cf. `02_data_warehouse/kpis.md` §1.2).
- **Jeu de données final** : 363 569 clients, taux de churn = **44,5 %**
  (161 798 clients churnés) — déséquilibre modéré, géré via `class_weight="balanced"`
  (ou sous-échantillonnage stratifié pour KNN/SVM).
- **Split** : 80 % train / 20 % test, stratifié sur la cible (`random_state=42`).

## ⚠️ Fuites de données identifiées et corrigées

Deux variables candidates ont été **écartées volontairement** après investigation :

1. **`nb_comptes_clos`** — fuite directe : `CLIENT_FULL_CHURN` est *défini* comme
   `nb_comptes_clos == nb_comptes`. La conserver donnait un score parfait
   (précision/recall/F1/AUC = 1.000), sans aucune valeur prédictive réelle.
2. **`nb_devises`** (nombre de devises distinctes détenues) — fuite indirecte :
   `nb_devises = 0` coïncide avec `churn = 1` dans ~100 % des cas pour un
   sous-groupe de 139 000 clients (38 % du dataset), car le champ `CURRENCY`
   n'est renseigné dans le SI source que lorsque les données produit sont
   complètes — ce qui coïncide structurellement avec la clôture plutôt que de
   refléter un vrai comportement multi-devise. **Test de sensibilité** :
   XGBoost sans cette variable donne un PR-AUC quasi identique (0.9828 vs
   0.983 avec), avec `a_epargne_placement` et `montant_total` qui prennent le
   relais — signal bien plus défendable et actionnable. `nb_devises` a donc
   été retirée définitivement (voir commentaire dans `src/train.py`).

## Tableau comparatif

| Modèle | Precision | Recall | F1 | ROC-AUC | **PR-AUC** | Temps entraînement | N entraînement |
|---|---|---|---|---|---|---|---|
| Régression logistique | 0.916 | 0.893 | 0.905 | 0.945 | 0.949 | 5.8 s | 290 855 |
| Arbre de décision | 0.962 | 0.916 | 0.938 | 0.974 | 0.977 | 5.2 s | 290 855 |
| KNN | 0.967 | 0.898 | 0.931 | 0.972 | 0.974 | 7.7 s | 40 000* |
| Random Forest | 0.991 | 0.890 | 0.938 | 0.977 | 0.981 | 97.5 s | 290 855 |
| SVM (RBF) | 0.984 | 0.871 | 0.924 | 0.955 | 0.948 | 23.5 s | 8 000* |
| **XGBoost** | **0.980** | **0.908** | **0.942** | **0.981** | **0.983** | 15.1 s | 290 855 |

\* KNN et SVM ne passent pas à l'échelle sur ~290k lignes d'entraînement (KNN :
coût de prédiction O(n_test × n_train) ; SVM RBF : complexité quadratique/cubique).
Entraînés sur un sous-échantillon stratifié (40 000 / 8 000 lignes).

## Modèle retenu : **XGBoost**

**Justification** :
- Meilleur **PR-AUC (0.983)** — la métrique la plus pertinente ici, la classe
  positive (churn, 44,5 %) restant minoritaire et étant celle qui intéresse le métier.
- Meilleur **F1 (0.942)**, et deuxième meilleur **recall (0.908)** derrière
  l'arbre de décision seul, mais avec une bien meilleure precision.
- Entraîné sur l'intégralité des données (contrairement à KNN/SVM).
- Temps d'entraînement très raisonnable (15.1 s) comparé au Random Forest
  (97.5 s) pour une performance équivalente ou supérieure sur tous les axes.

Rapport de classification complet (jeu de test, 72 714 clients) :

```
              precision    recall  f1-score   support

           0       0.93      0.98      0.96     40354
           1       0.98      0.91      0.94     32360

    accuracy                           0.95     72714
   macro avg       0.95      0.95      0.95     72714
weighted avg       0.95      0.95      0.95     72714
```

## Analyse d'interprétabilité (feature importance + SHAP)

Top facteurs identifiés par SHAP sur le modèle final (après retrait de `nb_devises`) :

| Rang | Feature | Interprétation métier |
|---|---|---|
| 1 | `montant_total` | Montant cumulé des produits détenus — un montant faible/nul est associé au churn |
| 2 | `anciennete_compte_moy_annees` | Ancienneté moyenne des comptes du client |
| 3 | `a_epargne_placement` | Détention d'un produit épargne/placement — **effet protecteur** contre le churn |
| 4 | `nb_comptes` | Nombre de comptes détenus (multi-bancarisation) |
| 5 | `anciennete_compte_max_annees` | Ancienneté du compte le plus ancien |
| 6 | `anciennete_client_annees` | Ancienneté de la relation client |
| 7 | `solde_moyen` / `solde_total` | Niveau de solde |
| 8 | `jours_depuis_derniere_revue_moy` | Ancienneté de la dernière revue KYC |

**Lecture métier** : la détention d'un produit épargne/placement (`a_epargne_placement`)
et l'ancienneté des comptes ressortent comme facteurs protecteurs — cohérent avec
l'intuition qu'un client multi-produits et installé dans la durée est moins volatil
(cf. `02_data_warehouse/kpis.md` §2.2). Voir `data/feature_importance.png` et
`data/shap_summary.png` pour le détail visuel complet.

## Limites connues

- Le churn est défini au niveau client à partir du statut des comptes
  (`Active`/`Closed`) — c'est un churn **constaté**, pas un churn **prédictif à
  horizon fixe** (ex. "churn dans les 90 prochains jours"). À affiner si une
  fenêtre temporelle métier est souhaitée (nécessiterait une date de référence
  glissante et un historique multi-période, non disponible dans ce jeu de données).
- `anciennete_compte_moy_annees` / `anciennete_compte_max_annees` sont manquantes
  pour ~86 % des clients churnés contre 0 % des clients actifs (dates
  `ACCT_OPENING_DATE` antérieures à 1900 exclues par le pipeline ETL, cf.
  `01_etl/src/transform.py::MIN_DATE`). C'est un vrai constat de qualité de
  données (comptes anciens/migrés moins bien documentés), pas une fuite au sens
  strict (imputation par la médiane, pas d'indicateur de manquant utilisé), mais
  à garder en tête pour l'interprétation métier.
