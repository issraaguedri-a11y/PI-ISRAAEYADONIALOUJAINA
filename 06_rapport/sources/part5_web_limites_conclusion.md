# 7. Interface web et déploiement

## 7.1 Objectifs et périmètre fonctionnel

L'application web a pour objectif d'exposer le modèle de churn et les analyses du projet à un utilisateur métier non technique, sans nécessiter d'installation ni de compétence en programmation. Conformément au périmètre minimal attendu, trois fonctionnalités ont été développées :

1. Des **KPIs de synthèse** sur la page d'accueil.
2. Une **analyse du churn par segment**, complémentaire du rapport Power BI.
3. Une **prédiction individuelle** (formulaire de saisie d'un profil client) et une **liste des comptes à risque** (prédiction en lot sur les clients actifs).

## 7.2 Choix technique

L'application est développée avec **Streamlit**, cohérent avec le choix de conserver Python comme langage unique sur l'ensemble de la chaîne (voir section 3.2). Ce choix a permis un développement rapide, l'équipe n'ayant pas eu à changer d'écosystème entre le pipeline ETL, la modélisation ML et l'interface de restitution.

Comme pour le pipeline ML, l'application interroge l'entrepôt PostgreSQL **en direct** à chaque affichage de page (pas de fichier CSV embarqué), avec une mise en cache des requêtes (10 minutes) pour limiter la charge sur la base sans sacrifier la fraîcheur des données affichées.

## 7.3 Page d'accueil — KPIs de synthèse

La page d'accueil affiche un état de santé du système (connexion à l'entrepôt, disponibilité du modèle), suivi des indicateurs clés : nombre de clients, nombre de comptes, taux de churn compte et taux de churn client, solde moyen, nombre de comptes clôturés, ainsi qu'une répartition rapide du portefeuille par statut et par secteur d'activité.

![Page d'accueil de l'application web](figures/webapp_accueil.png)

## 7.4 Analyse du churn par segment

Cette page reproduit, sous forme interactive et filtrable, les principaux axes de segmentation du churn déjà présents dans le rapport Power BI (âge, secteur d'activité, ancienneté), avec pour chaque segment le taux de churn et l'effectif associé affichés sous forme de graphique et de tableau détaillé.

![Page d'analyse du churn par segment](figures/webapp_analyse_churn.png)

## 7.5 Prédiction individuelle et comptes à risque

Cette page couvre les deux fonctionnalités centrales attendues :

**Prédiction individuelle** : deux modes de saisie sont proposés — la recherche d'un client existant par son identifiant (les features sont alors automatiquement récupérées depuis l'entrepôt), ou la saisie manuelle d'un profil complet, organisée par sections cohérentes avec l'analyse du modèle (profil socio-démographique, comportement bancaire, ancienneté, finances, produits détenus).

![Formulaire de prédiction individuelle](figures/webapp_prediction.png)

**Liste des comptes à risque** : une prédiction en lot est appliquée à l'ensemble des clients dont le dernier statut connu n'est pas déjà clôturé, avec un score de risque affiché pour chacun. La liste est filtrable par seuil de score et par secteur, triable par score décroissant, et exportable au format CSV pour une exploitation par les équipes de rétention.

## 7.6 Déploiement

Une procédure de déploiement sur Streamlit Community Cloud a été documentée (`05_web_app/DEPLOY.md`), incluant le point d'attention le plus critique : contrairement à une exécution locale, un déploiement cloud ne peut pas atteindre un PostgreSQL hébergé sur la machine de développement — la procédure détaille la mise en place d'un PostgreSQL public gratuit (Neon) et le rechargement des données via le pipeline ETL vers cette instance distante, ainsi que la gestion des secrets de connexion. À la date de rédaction de ce rapport, l'application est fonctionnelle en environnement local ; le déploiement public final est en cours de finalisation (voir section 8, limites).

\newpage

# 8. Limites et perspectives

## 8.1 Limites méthodologiques

**Définition du churn sans horizon temporel fixe.** Le churn tel que modélisé est un churn *constaté* (le client a, à la date des données, tous ses comptes clôturés) et non un churn *prédictif à horizon fixe* (par exemple, "le client churnera dans les 90 prochains jours"). Cette seconde formulation, plus proche d'un cas d'usage opérationnel de rétention proactive, nécessiterait une date de référence glissante et un historique multi-période que le jeu de données à disposition, en coupe unique, ne permet pas de construire.

**Valeurs manquantes structurelles sur l'ancienneté des comptes.** Les variables `ANCIENNETE_COMPTE_MOY_ANNEES` et `ANCIENNETE_COMPTE_MAX_ANNEES` sont manquantes pour environ 86 % des clients churnés contre 0 % des clients actifs, du fait du filtrage des dates d'ouverture antérieures à 1900 (section 4.1.2). Il ne s'agit pas d'une fuite de données au sens strict (l'imputation par la médiane ne transmet pas d'indicateur de valeur manquante au modèle), mais ce déséquilibre de complétude entre les deux classes doit être gardé à l'esprit dans l'interprétation des résultats, et pourrait justifier un travail de fiabilisation des dates anciennes côté système source.

**Catégories de compte majoritairement non renseignées.** Comme détaillé en section 5.4, 54,9 % des comptes n'ont pas de catégorie renseignée dans les données sources. Le taux de churn élevé associé à cette catégorie « Non renseigné » (58,2 %) est vraisemblablement le reflet d'une qualité de donnée dégradée plutôt qu'un vrai signal de risque métier — un point à ne pas sur-interpréter en l'état.

**Secteurs d'activité à faible effectif.** Certains secteurs d'activité affichant les taux de churn les plus extrêmes (proches de 100 %) ne comptent que quelques centaines de comptes. Ces résultats, bien que réels dans les données, doivent être interprétés avec prudence et ne constituent pas nécessairement un signal généralisable, contrairement au résultat sur la détention d'épargne (section 6.6), retrouvé de façon convergente sur l'ensemble du portefeuille par deux méthodes indépendantes.

## 8.2 Limites d'ingénierie

**Rapport Power BI partiellement finalisé.** Comme indiqué section 5.3, une page combinant vue d'ensemble et analyse du churn est opérationnelle ; la page dédiée à la segmentation client (profils, valeur, comptes à risque) reste à construire, bien que sa structure et ses mesures DAX soient d'ores et déjà documentées.

**Déploiement public de l'application web en cours de finalisation.** L'application est pleinement fonctionnelle en environnement local, connectée à l'entrepôt PostgreSQL local. Le déploiement sur Streamlit Community Cloud nécessite la mise en place d'un PostgreSQL accessible publiquement (section 7.6), étape en cours au moment de la rédaction de ce rapport.

**Absence d'optimisation des hyperparamètres.** Les modèles ont été entraînés avec des hyperparamètres raisonnables mais non systématiquement optimisés (pas de recherche en grille ou bayésienne). Un gain de performance supplémentaire, probablement marginal compte tenu des scores déjà élevés (PR-AUC 0,983), pourrait être obtenu par un réglage plus poussé du modèle XGBoost retenu.

## 8.3 Perspectives d'amélioration

- **Churn prédictif à horizon fixe** : si un historique multi-période devenait disponible, reformuler la cible en probabilité de churn à N jours plutôt qu'un constat de statut actuel, pour un usage opérationnel de rétention proactive plus direct.
- **Enrichissement transactionnel** : le référentiel de transactions mis à disposition (`dim_TRANSACTION`) n'a pas été exploité dans la version actuelle du pipeline ; l'intégration de features comportementales transactionnelles (fréquence, régularité des mouvements) constituerait une piste naturelle d'amélioration du pouvoir prédictif du modèle.
- **Suivi de la dérive du modèle** : en cas de mise en production réelle, mettre en place un suivi de la performance du modèle dans le temps (data drift, concept drift), le comportement client et les conditions macroéconomiques pouvant évoluer.
- **Étendre l'analyse SHAP** à des visualisations d'interaction entre variables (SHAP dependence plots), pour affiner la compréhension des effets croisés entre ancienneté, produits détenus et secteur d'activité.
- **Finaliser la page de segmentation Power BI** et le déploiement public de l'application web, les deux actions restant à court terme les plus directement actionnables pour compléter le périmètre du projet.

\newpage

# 9. Conclusion

Ce projet a permis de construire, de bout en bout, une chaîne décisionnelle complète pour l'analyse et la prédiction du churn client : de l'extraction et du nettoyage des données brutes jusqu'à une application web opérationnelle exposant un modèle prédictif, en passant par un entrepôt de données structuré et un rapport d'analyse Business Intelligence.

Le résultat le plus robuste du projet — la détention d'un produit d'épargne ou de placement comme facteur fortement protecteur contre le churn — a émergé de façon convergente par deux voies d'analyse indépendantes (analyse descriptive SQL/Power BI, interprétabilité SHAP du modèle prédictif), ce qui en fait une recommandation métier particulièrement défendable pour des actions de rétention ciblées.

Au-delà des résultats obtenus, le projet a été l'occasion d'exercer une rigueur méthodologique explicite : deux fuites de données ont été identifiées, investiguées par un test de sensibilité chiffré, documentées et corrigées plutôt que traitées superficiellement ; les limites et zones d'incertitude des données (complétude, effectifs faibles sur certains segments) sont rapportées avec la même transparence que les résultats positifs.

Les axes restant à finaliser — la page de segmentation Power BI et le déploiement public de l'application web — sont des extensions incrémentales d'une architecture déjà fonctionnelle de bout en bout, et ne remettent pas en cause la validité des analyses et du modèle prédictif présentés dans ce rapport.

\newpage

# Annexes

## A. Glossaire

| Terme | Définition |
|---|---|
| Churn | Attrition, perte d'un client (ici : clôture de la totalité de ses comptes) |
| ETL | Extract-Transform-Load, pipeline d'intégration de données |
| Grain | Niveau de détail d'une table de faits (ici : compte-produit ou client selon le contexte) |
| KYC | *Know Your Customer*, processus de connaissance client réglementaire |
| PR-AUC | Aire sous la courbe précision-rappel, métrique adaptée aux classes déséquilibrées |
| ROC-AUC | Aire sous la courbe ROC (*Receiver Operating Characteristic*) |
| SHAP | *SHapley Additive exPlanations*, méthode d'interprétabilité des modèles ML |
| Surrogate key (SK) | Clé de substitution technique, utilisée dans les schémas dimensionnels |

## B. Structure du dépôt de code

Le code source complet est disponible sur le dépôt GitHub du projet : `https://github.com/issraaguedri-a11y/PI-ISRAAEYADONIALOUJAINA`.

| Dossier | Contenu |
|---|---|
| `00_documentation/` | Documents de cadrage fournis par l'encadrant |
| `01_etl/` | Pipeline d'extraction, nettoyage et transformation des données |
| `02_data_warehouse/` | Schéma SQL, scripts de chargement, documentation des KPIs |
| `03_power_bi/` | Guide de construction et mesures DAX du rapport Power BI |
| `04_machine_learning/` | Notebooks et scripts d'entraînement, comparaison des modèles, modèle final |
| `05_web_app/` | Application Streamlit et procédure de déploiement |
| `06_rapport/` | Le présent rapport (sources Markdown/LaTeX et version PDF) |
| `07_presentation/` | Slides de présentation |

Chaque dossier dispose d'un `README.md` détaillant les étapes d'exécution et les éventuels prérequis, pour permettre à un tiers de reproduire l'intégralité du pipeline.

## C. Références des outils utilisés

- **Python** 3.13, **pandas**, **SQLAlchemy**, **psycopg2** pour l'ETL et l'accès aux données.
- **PostgreSQL** 16 comme entrepôt de données analytique.
- **Power BI Desktop** pour les tableaux de bord.
- **scikit-learn**, **XGBoost**, **SHAP** pour la modélisation et l'interprétabilité.
- **Streamlit** pour l'application web.
- **Git** et **GitHub** pour le versioning et la collaboration.
