# 5. Analyses BI et tableaux de bord Power BI

## 5.1 Démarche

Le rapport Power BI se connecte à l'entrepôt `churn_dw` (dans sa version la plus récente, via un export CSV des 7 tables de l'entrepôt afin de simplifier la configuration du poste de travail, sans changer ni le contenu ni la définition des indicateurs par rapport à une connexion PostgreSQL directe — voir `03_power_bi/README.md`). Les relations entre la table de faits et les dimensions ont été reconstruites dans Power BI selon le même schéma en étoile que celui de l'entrepôt (section 4.2).

L'ensemble des mesures DAX utilisées est documenté dans `03_power_bi/measures_dax.md`, avec pour chacune une explication de sa logique métier plutôt qu'une simple formule brute — un choix qui facilite la relecture et la maintenance du rapport par un tiers.

## 5.2 KPIs retenus

Les indicateurs suivants ont été définis, cohérents avec ceux utilisés par ailleurs dans le projet (entrepôt SQL, modélisation ML) :

- **Taux de churn compte** : proportion de lignes compte-produit dont le compte est clôturé (37,4 % sur l'ensemble du portefeuille).
- **Taux de churn client (full churn)** : proportion de clients dont tous les comptes sont clôturés (44,5 %) — l'indicateur le plus représentatif d'une perte de relation client complète.
- **Répartition par secteur d'activité** : le taux de churn varie fortement d'un secteur à l'autre, certains secteurs peu représentés atteignant des taux proches de 100 % (à interpréter avec prudence compte tenu de leur faible effectif, voir section 8).
- **Répartition des motifs de clôture** : plus de 70 % des clôtures sont associées à un motif générique (« Autre ») ou non renseigné, ce qui limite la capacité d'analyse fine des causes de churn côté système source.
- **Évolution mensuelle des clôtures** : mise en évidence de pics ponctuels, à confronter à des événements métier (campagnes, changements de politique commerciale) que les données à disposition ne permettent pas d'identifier avec certitude.

## 5.3 État d'avancement du rapport Power BI

À la date de rédaction de ce rapport, une page opérationnelle a été construite, combinant les indicateurs clés (cartes de synthèse), la répartition du churn par secteur d'activité, la répartition des motifs de clôture et l'évolution temporelle des clôtures :

![Page Power BI — Vue d'ensemble et analyse du churn](figures/powerbi_vue_ensemble.png)

Conformément au guide du projet, deux axes d'analyse complémentaires restent à finaliser dans une page dédiée à la segmentation client (profils, valeur client, comptes à risque) — la structure de cette page ainsi que les mesures DAX nécessaires sont d'ores et déjà documentées et prêtes à l'implémentation (`03_power_bi/measures_dax.md`, bloc 5 : détention de produits, bloc 3 : regroupement des catégories de compte). Le tableau de correspondance mesure/visuel du même document sert de feuille de route pour cette finalisation.

## 5.4 Regroupement des catégories de compte

Un travail spécifique a été mené pour rendre exploitable la variable `ACCOUNT_CATEGORY_LABEL`, qui compte près de 150 modalités distinctes dans les données sources — dont plus de la moitié sans libellé renseigné (« Non disponible ») et le reste réparti en de très nombreuses catégories très fines (ex. « CPTE SOUS DELAG.DE CHANGE », quelques dizaines de comptes). Un tel niveau de détail rend toute visualisation illisible.

Ces catégories ont été regroupées en 7 familles métier (colonne calculée `Famille Compte`, cf. `03_power_bi/measures_dax.md`), avec un résultat particulièrement parlant :

| Famille | Part du portefeuille | Taux de churn |
|---|---|---|
| Non renseigné | 54,9 % | 58,2 % |
| **Épargne** | 36,5 % | **8,6 %** |
| Compte courant / dépôt à vue | 6,8 % | 24,1 % |
| Allocation touristique / change | 0,7 % | 40,6 % |
| Compte indisponible / bloqué | 0,6 % | 40,9 % |
| Compte professionnel | 0,3 % | 47,8 % |
| Autre | 0,2 % | 21,0 % |

Ce résultat est l'un des constats les plus robustes du projet : la détention d'un produit d'épargne ou de placement est associée à un taux de churn nettement inférieur à toutes les autres familles de comptes. Ce même signal ressort indépendamment de l'analyse d'interprétabilité du modèle Machine Learning (section 6.6), ce qui renforce la confiance dans ce constat — il n'est pas un artefact d'une seule méthode d'analyse.

À l'inverse, la part très importante de comptes « Non renseigné » (54,9 % du portefeuille) est davantage un indicateur de qualité de données côté système source qu'un vrai signal métier ; son taux de churn élevé (58,2 %) doit être interprété avec cette réserve plutôt que comme une catégorie de risque en tant que telle (approfondi section 8).
