# 6. Modélisation Machine Learning

## 6.1 Objectif et grain de la modélisation

L'objectif est de prédire, pour un client donné, sa probabilité de churn complet (`CLIENT_FULL_CHURN`, voir section 2.3). Contrairement aux analyses BI menées au grain compte-produit, la modélisation prédictive se place au **grain client** : chaque ligne du jeu de données d'entraînement représente un client, ses features résultant d'une agrégation SQL de l'ensemble de ses comptes et produits.

Ce choix de grain a une conséquence méthodologique importante, développée en 6.2 : plusieurs variables candidates, naturellement disponibles au niveau compte, deviennent des risques de fuite de données une fois agrégées au niveau client, car elles peuvent se retrouver mécaniquement corrélées — voire identiques — à la définition de la cible.

## 6.2 Préparation des données et fuites de données identifiées

### 6.2.1 Construction du jeu de données

Le jeu de données d'entraînement est construit par une requête SQL unique (`04_machine_learning/src/prepare_data.py`), qui agrège directement les données de l'entrepôt PostgreSQL par client (`GROUP BY CUSTOMER_NO`), sans étape intermédiaire de fichier CSV caché. Cette requête produit **363 569 lignes** (une par client), avec des features couvrant :

- Le profil socio-démographique (âge, nationalité, résidence, statut marital, secteur d'activité principal).
- Le comportement bancaire (nombre de comptes, nombre de produits distincts, ancienneté).
- Les indicateurs financiers (solde total et moyen, salaire déclaré, montant total des produits).
- La détention de types de produits (crédit, épargne/placement, compte courant, coffre).

### 6.2.2 Fuites de données identifiées et corrigées

Un travail de vigilance méthodologique a permis d'identifier deux fuites de données au cours du premier essai d'entraînement, documentées et corrigées plutôt que masquées :

**Fuite directe — `NB_COMPTES_CLOS`.** Cette variable a été initialement incluse comme feature candidate. Or `CLIENT_FULL_CHURN` est *défini* comme `NB_COMPTES_CLOS = NB_COMPTES` : la conserver revient à donner au modèle la réponse dans l'énoncé. Le premier essai d'entraînement avec cette variable a donné un score parfait sur toutes les métriques (précision, rappel, F1, AUC = 1,000), un signal sans ambiguïté de fuite de données. La variable a été retirée.

**Fuite indirecte — `NB_DEVISES`.** Le nombre de devises distinctes détenues par le client est apparu comme la variable la plus prédictive lors d'un deuxième essai, avec une importance disproportionnée (SHAP). Une investigation a montré que `NB_DEVISES = 0` coïncidait avec `CHURN = 1` dans près de 100 % des cas pour un sous-groupe de 139 000 clients (38 % du jeu de données) — non pas parce que l'absence de multi-devise cause le churn, mais parce que le champ `CURRENCY` n'est renseigné dans le système source que lorsque les données produit sont complètes, ce qui coïncide structurellement avec la clôture du compte plutôt que de refléter un comportement client réel. Un **test de sensibilité** a permis de trancher : un modèle XGBoost entraîné sans cette variable obtient un PR-AUC quasi identique (0,9828 contre 0,983 avec), la variable `A_EPARGNE_PLACEMENT` et `MONTANT_TOTAL` prenant alors le relais dans l'importance des features — un signal bien plus défendable d'un point de vue métier. La variable a été retirée définitivement.

Cette démarche — détecter, investiguer par un test chiffré, documenter, corriger — est jugée plus rigoureuse qu'un simple retrait a priori de variables suspectes sans vérification, et plus honnête qu'une conservation non questionnée de variables donnant d'excellents résultats sans en comprendre la cause.

### 6.2.3 Encodage et prétraitement

Le prétraitement est encapsulé dans un pipeline scikit-learn (`ColumnTransformer`), garantissant que les mêmes transformations sont appliquées de façon identique à l'entraînement et à l'inférence (application web) :

- **Variables numériques** : imputation des valeurs manquantes par la médiane, puis standardisation (`StandardScaler`).
- **Variables catégorielles** : imputation par une modalité `"Inconnu"`, puis encodage one-hot (`OneHotEncoder`, avec gestion des modalités inconnues en inférence).
- **Modalités rares** : les modalités peu fréquentes de nationalité, résidence et secteur d'activité sont regroupées sous une catégorie `"Autre"` avant encodage, pour limiter la dimensionnalité introduite par le one-hot encoding.

### 6.2.4 Gestion du déséquilibre de classes

Le taux de churn client (44,5 %) constitue un déséquilibre modéré plutôt que sévère. Il a été traité par pondération des classes (`class_weight="balanced"`) plutôt que par un rééchantillonnage synthétique (SMOTE), ce dernier n'apparaissant pas nécessaire compte tenu du déséquilibre limité et présentant un risque de créer des exemples synthétiques peu réalistes sur des variables catégorielles à haute cardinalité.

### 6.2.5 Séparation train / test

Un découpage stratifié 80 % / 20 % a été retenu (`random_state=42` pour la reproductibilité), soit environ 290 855 clients pour l'entraînement et 72 714 pour l'évaluation.

## 6.3 Modèles entraînés et métriques d'évaluation

Six modèles de classification ont été entraînés et comparés, couvrant un spectre de complexité et de familles algorithmiques différentes : régression logistique (référence linéaire), k plus proches voisins, arbre de décision, forêt aléatoire, machine à vecteurs de support (noyau RBF), et XGBoost.

Compte tenu du déséquilibre de classes, l'évaluation ne s'est pas limitée à l'exactitude (*accuracy*), peu informative dans ce contexte, mais a mobilisé un ensemble de métriques adaptées : précision, rappel, F1-score, aire sous la courbe ROC (ROC-AUC) et surtout **aire sous la courbe précision-rappel (PR-AUC)**, la métrique la plus pertinente lorsque la classe positive présente un intérêt métier particulier — ici, identifier les clients à risque de churn.

**Limite de comparabilité** : les modèles KNN et SVM ne passent pas à l'échelle sur l'intégralité du jeu d'entraînement (coût de prédiction en O(n_test × n_train) pour KNN ; complexité quadratique à cubique en entraînement pour un noyau RBF). Ils ont donc été entraînés sur un sous-échantillon stratifié (respectivement 40 000 et 8 000 lignes), ce qui est indiqué explicitement dans le tableau ci-dessous et doit être gardé à l'esprit dans l'interprétation de leurs résultats.

| Modèle | Précision | Rappel | F1 | ROC-AUC | **PR-AUC** | Temps d'entraînement | N entraînement |
|---|---|---|---|---|---|---|---|
| Régression logistique | 0,916 | 0,893 | 0,905 | 0,945 | 0,949 | 5,8 s | 290 855 |
| Arbre de décision | 0,962 | 0,916 | 0,938 | 0,974 | 0,977 | 5,2 s | 290 855 |
| K plus proches voisins | 0,967 | 0,898 | 0,931 | 0,972 | 0,974 | 7,7 s | 40 000* |
| Forêt aléatoire | 0,991 | 0,890 | 0,938 | 0,977 | 0,981 | 97,5 s | 290 855 |
| SVM (noyau RBF) | 0,984 | 0,871 | 0,924 | 0,955 | 0,948 | 23,5 s | 8 000* |
| **XGBoost** | **0,980** | **0,908** | **0,942** | **0,981** | **0,983** | 15,1 s | 290 855 |

\*Sous-échantillon stratifié (voir limite ci-dessus).

![Comparaison des 6 modèles sur les cinq métriques d'évaluation](figures/models_comparison.png)

## 6.4 Modèle retenu

Le modèle **XGBoost** a été retenu comme modèle final, pour les raisons suivantes :

1. **Meilleur PR-AUC (0,983)**, la métrique jugée la plus pertinente compte tenu du déséquilibre de classes et de l'intérêt métier porté à la classe positive.
2. **Meilleur F1-score (0,942)**, avec un rappel (0,908) élevé sans sacrifier excessivement la précision — un compromis important pour une application de rétention client, où un faux négatif (client qui churn sans avoir été identifié) a un coût métier réel.
3. Entraîné sur l'intégralité des données disponibles, contrairement à KNN et SVM.
4. Temps d'entraînement très raisonnable (15,1 secondes) comparé à la forêt aléatoire (97,5 secondes) pour une performance égale ou supérieure sur l'ensemble des métriques.

La forêt aléatoire obtient une précision légèrement supérieure mais un rappel plus faible, pour un temps d'entraînement environ 6 fois supérieur — le compromis performance/coût de calcul penche nettement en faveur de XGBoost.

## 6.5 Rapport de classification détaillé

Sur le jeu de test (72 714 clients) :

| | Précision | Rappel | F1-score | Support |
|---|---|---|---|---|
| Classe 0 (actif) | 0,93 | 0,98 | 0,96 | 40 354 |
| Classe 1 (churné) | 0,98 | 0,91 | 0,94 | 32 360 |
| **Exactitude** | | | **0,95** | 72 714 |
| Moyenne macro | 0,95 | 0,95 | 0,95 | 72 714 |
| Moyenne pondérée | 0,95 | 0,95 | 0,95 | 72 714 |

## 6.6 Interprétabilité

L'interprétabilité du modèle final a été menée par deux approches complémentaires : l'importance native des features (gain XGBoost) et les valeurs SHAP (*SHapley Additive exPlanations*), calculées sur un échantillon de 2 000 clients du jeu de test.

![Résumé SHAP des features du modèle final](figures/shap_summary.png)

![Importance des features (gain XGBoost)](figures/feature_importance.png)

Les principaux facteurs prédictifs identifiés, une fois les fuites de données de la section 6.2.2 corrigées, sont :

1. **`MONTANT_TOTAL`** — montant cumulé des produits détenus par le client. Un montant faible ou nul est associé au churn.
2. **`ANCIENNETE_COMPTE_MOY_ANNEES`** — ancienneté moyenne des comptes du client.
3. **`A_EPARGNE_PLACEMENT`** — détention d'un produit d'épargne ou de placement, qui ressort comme un facteur **protecteur** contre le churn.
4. **`NB_COMPTES`** — nombre de comptes détenus (multi-bancarisation).
5. **`ANCIENNETE_COMPTE_MAX_ANNEES`**, **`ANCIENNETE_CLIENT_ANNEES`**, **`SOLDE_MOYEN`**, **`SOLDE_TOTAL`** — ancienneté et niveau de solde, dans l'ordre d'importance décroissante.

**Convergence avec l'analyse descriptive.** Le facteur protecteur associé à la détention d'un produit d'épargne ou de placement, identifié ici par SHAP, est retrouvé de façon indépendante dans l'analyse Power BI (section 5.4) : les comptes de la famille « Épargne » affichent un taux de churn observé de 8,6 %, contre 24 à 58 % pour les autres familles de comptes. Cette convergence entre deux méthodes d'analyse indépendantes — l'une descriptive et agrégée, l'autre issue de l'interprétabilité d'un modèle prédictif entraîné au grain client — renforce la confiance dans ce constat et en fait une recommandation actionnable prioritaire pour des actions de rétention ciblées.

## 6.7 Sauvegarde et intégration du modèle

Le modèle final, incluant l'intégralité du pipeline de prétraitement, est sérialisé avec `joblib` (`04_machine_learning/models/model_final.joblib`, environ 1 Mo). Ce choix garantit que l'inférence en production (application web, section 7) applique exactement les mêmes transformations qu'à l'entraînement, sans risque de divergence entre les deux environnements. Les versions de `scikit-learn` et `XGBoost` utilisées à l'entraînement sont épinglées dans les dépendances de l'application web, pour éviter toute incompatibilité de désérialisation du modèle liée à un changement de version.
