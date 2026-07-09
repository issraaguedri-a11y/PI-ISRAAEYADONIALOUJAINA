# 3. Architecture de la solution

## 3.1 Vue d'ensemble

La solution repose sur une chaîne de traitement linéaire, où chaque composante consomme la sortie de la précédente : les données brutes sont nettoyées et enrichies par un pipeline ETL, chargées dans un entrepôt de données PostgreSQL modélisé en étoile, puis exploitées en parallèle par deux voies de restitution — l'analyse descriptive via Power BI, et la modélisation prédictive via un pipeline Machine Learning dont le modèle final est exposé par une application web.

![Architecture globale de la solution](figures/architecture.png)

Un choix structurant du projet a été de faire de **PostgreSQL la source de vérité unique** pour l'ensemble des composantes en aval (Power BI, Machine Learning, application web) plutôt que de dupliquer des exports CSV intermédiaires. Concrètement, `04_machine_learning/src/prepare_data.py` construit le jeu de données d'entraînement par une requête SQL d'agrégation directe sur l'entrepôt (pas de fichier CSV intermédiaire caché), et `05_web_app` interroge ce même entrepôt en temps réel à chaque affichage de page. Ce choix garantit qu'il n'existe qu'une seule définition du churn et qu'un seul jeu de features dans tout le projet.

## 3.2 Justification des choix techniques

| Composante | Choix retenu | Justification |
|---|---|---|
| Langage principal | Python 3.13 | Écosystème data science complet, cohérence entre ETL, ML et application web |
| Entrepôt de données | PostgreSQL | Base relationnelle mature, requêtable directement par Power BI et par le pipeline ML, plus proche d'un contexte de production qu'une base fichier |
| Manipulation de données | pandas | Standard de facto, suffisant pour la volumétrie du projet (< 1 million de lignes) |
| Modélisation dimensionnelle | Schéma en étoile | Grain compte-produit, dimensions dénormalisées — optimisé pour les requêtes analytiques de Power BI et les agrégations SQL du pipeline ML |
| Visualisation BI | Power BI Desktop | Imposé par l'énoncé du projet |
| Modélisation ML | scikit-learn + XGBoost | Couverture des familles de modèles classiques et boostés, API cohérente (pipelines scikit-learn) |
| Interface web | Streamlit | Développement rapide en Python pur, cohérent avec le reste de la stack, sans changement de langage pour l'équipe |
| Versioning | Git + GitHub | Imposé par l'énoncé du projet |

## 3.3 Flux de données de bout en bout

1. **Extraction** : lecture du fichier CSV principal et des tables de dimensions Excel.
2. **Transformation** : nettoyage, déduplication, jointures avec les dimensions, calcul de variables dérivées (âge, ancienneté, indicateurs de qualité).
3. **Chargement** : écriture dans les 7 tables du schéma en étoile de l'entrepôt PostgreSQL `churn_dw`.
4. **Consommation BI** : Power BI se connecte directement à l'entrepôt et calcule ses mesures en DAX.
5. **Consommation ML** : le pipeline de préparation de données interroge l'entrepôt par une requête SQL d'agrégation (grain client), entraîne et évalue plusieurs modèles, puis sérialise le modèle final retenu.
6. **Consommation applicative** : l'application web interroge l'entrepôt pour les KPIs et les listes de clients, et charge le modèle sérialisé pour la prédiction.

\newpage

# 4. ETL et modélisation dimensionnelle

## 4.1 Pipeline ETL

Le pipeline ETL est implémenté en Python (pandas), organisé en trois modules distincts correspondant aux trois étapes classiques Extract-Transform-Load, orchestrés par un script principal (`01_etl/pipeline.py`) qui peut s'exécuter sur l'intégralité des données ou sur un échantillon (paramètre `--sample`, utile pour les tests rapides en développement).

### 4.1.1 Extraction (`extract.py`)

Cette étape charge le fichier CSV principal ainsi que les quatre tables de dimensions Excel utilisées par le pipeline (catégories de compte, devises, motifs de clôture, secteurs d'activité). Chaque chargement est accompagné d'un contrôle de cohérence (nombre de lignes chargées, colonnes présentes) journalisé en sortie.

### 4.1.2 Transformation (`transform.py`)

C'est l'étape la plus substantielle du pipeline. Elle réalise, dans l'ordre :

- **Déduplication** : suppression des lignes strictement dupliquées (38 640 lignes supprimées sur les 528 883 lignes source).
- **Normalisation des dates** : conversion des dates au format `YYYYMMDD` en type `datetime`, avec filtrage des dates aberrantes antérieures au 1er janvier 1900 (`MIN_DATE`), traitées comme des valeurs de remplissage technique plutôt que des dates réelles.
- **Jointures avec les dimensions** : enrichissement du fichier principal avec les libellés descriptifs (secteur d'activité, devise, motif de clôture, catégorie de compte) à partir des codes présents dans les données sources.
- **Calcul de variables dérivées** :
  - `AGE` à partir de l'année de naissance.
  - `CLIENT_SENIORITY_YEARS` et `ACCOUNT_SENIORITY_YEARS` (ancienneté en années, calculée par rapport à une date de référence).
  - `DAYS_SINCE_LAST_REVIEW` (fraîcheur du dossier KYC).
  - `NB_COMPTES`, `NB_PRODUITS_DISTINCTS`, `NB_COMPTES_CLOS` (agrégats de multi-bancarisation par client).
  - `CHURN` et `CLIENT_FULL_CHURN` (variables cibles, voir section 2.3).
  - `FLAG_INCOHERENCE_CLOTURE` (indicateur de qualité de données, sans masquer l'anomalie détectée).
- **Contrôle de cohérence final** : vérification du nombre de lignes, du taux de valeurs manquantes par colonne, et du taux de churn obtenu, journalisés en sortie du pipeline.

### 4.1.3 Chargement (`load.py`)

Cette étape construit les 7 tables du schéma en étoile à partir du DataFrame transformé (génération des clés de substitution — *surrogate keys* — pour chaque dimension), puis les charge dans PostgreSQL. Pour la table de faits (490 243 lignes), le chargement utilise la commande `COPY` de PostgreSQL plutôt que des insertions ligne par ligne, ce qui réduit le temps de chargement complet à quelques dizaines de secondes contre plusieurs minutes avec une approche par insertions unitaires.

## 4.2 Modèle dimensionnel

Le schéma retenu est un schéma en étoile classique : une table de faits centrale, `fact_compte_client`, entourée de six tables de dimensions.

![Schéma en étoile de l'entrepôt churn_dw](figures/star_schema.png)

**Grain de la table de faits** : un couple (client, compte-produit) — cohérent avec le grain du fichier source, et suffisamment fin pour permettre à la fois les analyses au niveau compte (Power BI) et l'agrégation au niveau client (Machine Learning) sans perte d'information.

| Table | Rôle | Volumétrie |
|---|---|---|
| `fact_compte_client` | Table de faits — 1 ligne = 1 compte-produit | 490 243 lignes |
| `dim_client` | Attributs socio-démographiques du client | 363 569 lignes |
| `dim_industry` | Secteur d'activité du client | 644 lignes |
| `dim_currency` | Devise du compte | 19 lignes |
| `dim_closure_reason` | Motif de clôture du compte | 19 lignes |
| `dim_account_category` | Catégorie du compte | 149 lignes |
| `dim_date` | Dimension calendaire (dates d'ouverture, de clôture) | 13 070 lignes |

Les scripts SQL de création du schéma (`02_data_warehouse/schema/create_tables.sql`) définissent les clés primaires, contraintes de clé étrangère, et index sur les colonnes de jointure les plus fréquemment utilisées (clés de substitution, `CUSTOMER_NO`, `ACCOUNT_NO`, indicateur `CHURN`).

## 4.3 Contrôles de cohérence et de qualité

Au-delà des traitements de nettoyage décrits en 4.1.2, le pipeline documente explicitement les problèmes de qualité résiduels plutôt que de les masquer :

- Le taux de churn obtenu après transformation (37,4 % au niveau compte, 44,5 % au niveau client) est vérifié à chaque exécution du pipeline et journalisé, pour détecter toute dérive anormale entre deux exécutions.
- L'indicateur `FLAG_INCOHERENCE_CLOTURE` trace les comptes présentant une incohérence entre statut et motif de clôture, sans les exclure du jeu de données — un choix délibéré pour ne pas biaiser la volumétrie, la correction de fond de ces incohérences relevant du système source et non du pipeline analytique.
- La proportion de comptes sans catégorie renseignée (`Non disponible`, ~55 % des lignes) est également documentée telle quelle, avec les implications de ce constat discutées section 8.
