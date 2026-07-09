# Résumé exécutif

Ce projet propose une chaîne décisionnelle complète pour comprendre, mesurer et anticiper l'attrition (*churn*) de la clientèle d'une institution bancaire, à partir d'un jeu de données réel et anonymisé de **528 883 lignes** (couples client-compte-produit), portant sur **363 569 clients**.

La solution mise en œuvre couvre les cinq composantes attendues : un pipeline ETL reproductible qui nettoie et enrichit les données brutes ; un entrepôt de données PostgreSQL modélisé en étoile ; un rapport Power BI d'analyse descriptive du churn ; un modèle de Machine Learning (XGBoost) qui prédit la probabilité de churn d'un client avec un **PR-AUC de 0,983** ; et une application web Streamlit qui expose ce modèle et ces analyses à un utilisateur métier.

Le taux de churn observé au niveau client (tous comptes clôturés) est de **44,5 %**. L'analyse a mis en évidence un facteur protecteur particulièrement net : les clients détenant un produit d'épargne ou de placement affichent un taux de churn de l'ordre de 8 % contre plus de 40 % pour les autres — un résultat convergent, retrouvé à la fois dans l'analyse descriptive (Power BI, SQL) et dans l'interprétabilité du modèle prédictif (SHAP).

Une attention particulière a été portée à la rigueur méthodologique : deux fuites de données ont été identifiées et corrigées en cours de modélisation (une variable définissant littéralement la cible, une autre corrélée à un artefact de complétude du système source plutôt qu'à un vrai comportement client), documentées avec un test de sensibilité chiffré plutôt que simplement écartées sans justification.

L'ensemble du code est disponible sur un dépôt GitHub public, structuré en composantes numérotées, chacune dotée d'un README détaillé permettant la reproduction complète du pipeline par un tiers.

\newpage

# 1. Introduction et contexte

## 1.1 Contexte métier

La fidélisation client est un enjeu majeur du secteur bancaire : la littérature professionnelle du secteur estime qu'acquérir un nouveau client coûte significativement plus cher que d'en conserver un existant. Anticiper le départ d'un client — le *churn* — permet de déclencher des actions de rétention ciblées avant qu'il ne soit trop tard, plutôt que de subir l'attrition de manière passive.

Ce projet s'inscrit dans le cadre du Projet Intégré du Master 1 Business Analytics d'ESPRIT School of Business. Une institution bancaire (dont l'identité n'est pas mentionnée dans ce document, conformément aux règles de confidentialité du projet) a mis à disposition un extrait anonymisé de son système d'information : informations clients, comptes et produits, sur plusieurs années d'historique.

## 1.2 Objectif du projet

L'objectif est de concevoir, de bout en bout, une solution analytique complète permettant de :

1. **Comprendre** le churn : quels segments de clientèle sont les plus exposés, quels facteurs y sont associés.
2. **Mesurer** le churn : le quantifier de façon fiable et le restituer via des indicateurs métier exploitables.
3. **Anticiper** le churn : prédire, pour un client donné, sa probabilité de churn à l'aide d'un modèle supervisé.
4. **Restituer** ces analyses à des utilisateurs non techniques via des tableaux de bord et une application web.

## 1.3 Démarche et organisation

Le projet a été mené sur 4 semaines, avec une progression suivant la chaîne de valeur analytique classique : exploration des données, ETL, modélisation dimensionnelle, Business Intelligence, Machine Learning, puis interface de restitution. Cette organisation correspond à la structure numérotée du dépôt de code (`01_etl` à `07_presentation`).

Le travail a été mené en équipe de 4, avec une répartition des rôles centrée sur les compétences de chacune : ingénierie des données et Machine Learning en binôme, Business Intelligence, et structuration des livrables finaux (rapport, présentation). Le détail de la répartition figure dans le README principal du dépôt.

## 1.4 Structure du présent document

Ce rapport suit la structure recommandée par le guide du projet : après cette introduction, la section 2 décrit et explore les données sources. La section 3 présente l'architecture globale de la solution. La section 4 détaille le pipeline ETL et la modélisation dimensionnelle. La section 5 présente les analyses Business Intelligence et le rapport Power BI. La section 6 constitue le cœur méthodologique du projet : la modélisation Machine Learning, de la préparation des données à l'interprétabilité du modèle final. La section 7 présente l'application web et son déploiement. La section 8 discute des limites du travail réalisé et des perspectives d'amélioration, avant la conclusion.

\newpage

# 2. Description et exploration des données

## 2.1 Origine et volumétrie

Les données mises à disposition proviennent du système d'information d'une institution bancaire et ont été anonymisées avant remise aux équipes projet : aucun identifiant personnel direct n'est exploitable (les identifiants clients et comptes ont été remplacés par des séquences artificielles), mais la structure et la cohérence métier des données ont été préservées.

Le jeu de données est composé de :

- **Un fichier principal** au format CSV, contenant les informations clients, comptes et produits, avant nettoyage.
- **Huit tables de dimensions** au format Excel, donnant le libellé descriptif associé aux codes présents dans le fichier principal (catégorie de compte, devise, motif de clôture, secteur d'activité, segment cible, secteur détaillé, référentiel transaction, référentiel agence).

Chaque ligne du fichier principal correspond à un couple **(client, compte-produit)** : un même client peut apparaître plusieurs fois s'il détient plusieurs comptes ou produits.

| Indicateur | Valeur |
|---|---|
| Lignes brutes (avant nettoyage) | 528 883 |
| Doublons identifiés et supprimés | 38 640 |
| Lignes finales (table de faits) | 490 243 |
| Clients uniques | 363 569 |
| Colonnes du fichier final (après enrichissement) | 36 |

## 2.2 Principales variables

Le fichier principal regroupe quatre familles de variables :

**Identifiants** — `CUSTOMER_NO`, `ACCOUNT_NO`, `BRANCH` (agence de rattachement).

**Informations client** — nationalité, résidence, statut marital, année de naissance, nature du client (personne physique / morale), classification commerciale (`PARTYCLASS` : Retail, Corporate...), ligne métier, score KYC (*Know Your Customer*), complétude du dossier, secteur d'activité, salaire déclaré.

**Informations compte** — statut du compte (`ACCOUNT_STATUS`, *Active*/*Closed* — base de la variable cible), dates d'ouverture et de clôture, catégorie de compte, devise, motif de clôture, solde.

**Informations produit** — groupe de produits, ligne de produits, produit spécifique.

## 2.3 Définition de la variable cible

Deux niveaux de churn ont été retenus, cohérents avec le grain différent de l'analyse descriptive (niveau compte-produit) et de la modélisation prédictive (niveau client) :

- **`CHURN`** (niveau compte-produit) : 1 si le compte est au statut *Closed*, 0 sinon. Utilisé pour les analyses de répartition par produit, secteur, devise.
- **`CLIENT_FULL_CHURN`** (niveau client) : 1 si **tous** les comptes du client sont clôturés (`NB_COMPTES_CLOS = NB_COMPTES`), 0 sinon. C'est un signal plus fort qu'un churn partiel d'un client multi-comptes, et c'est la variable retenue comme cible du modèle prédictif (section 6).

Sur le jeu de données final : **37,4 %** des lignes compte-produit sont en churn, et **44,5 %** des clients sont en churn complet — un déséquilibre de classes modéré mais réel, qui a orienté le choix des métriques d'évaluation du modèle (section 6.3).

## 2.4 Qualité des données et problèmes identifiés

L'exploration initiale a mis en évidence plusieurs problèmes de qualité, traités explicitement dans le pipeline ETL (détaillé section 4) :

- **38 640 doublons** dans le fichier source, supprimés avant chargement.
- **Dates aberrantes** : certaines dates d'ouverture de compte antérieures à 1900 (vraisemblablement des valeurs de remplissage technique plutôt que de vraies dates), filtrées via un seuil `MIN_DATE = 1900-01-01`.
- **Incohérences de clôture** : des comptes marqués comme clôturés sans motif de clôture renseigné, ou l'inverse — un indicateur `FLAG_INCOHERENCE_CLOTURE` a été créé pour tracer ce phénomène sans le masquer.
- **Valeurs catégorielles manquantes non uniformisées** : certains champs texte utilisaient des valeurs de remplissage variées (chaînes vides, codes `UNKNOWN`, valeurs `NULL` textuelles) selon la colonne, uniformisées lors de la transformation.
- **Une part significative de comptes sans catégorie de compte renseignée** (`ACCOUNT_CATEGORY_LABEL = "Non disponible"`, ~55 % des lignes) — un constat rapporté tel quel plutôt que masqué, avec ses implications discutées section 8 (limites).

Ces choix de traitement sont documentés en détail dans le code source du module de transformation (`01_etl/src/transform.py`) et dans le dictionnaire de données du dépôt.
