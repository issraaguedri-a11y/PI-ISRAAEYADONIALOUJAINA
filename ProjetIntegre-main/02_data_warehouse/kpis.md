# KPIs — Data Warehouse Churn Client

Ce document liste les indicateurs clés (KPIs) calculés à partir du modèle en
étoile (`fact_compte_client` + dimensions). Chaque KPI est défini par :
sa formule métier, la formule SQL correspondante (sur les tables du DW), et
son usage (BI / reporting ou feature ML).

Rappel du grain de `fact_compte_client` : **une ligne = un compte-produit**
(un même client peut avoir plusieurs comptes, un même compte plusieurs
produits). C'est pourquoi certains KPIs distinguent le niveau *compte-produit*
du niveau *client*.

---

## 1. KPIs de Churn (indicateur cible)

### 1.1 Taux de churn global (niveau compte-produit)
Proportion de lignes compte-produit dont le compte est clôturé.

**Formule métier** : `CHURN = 1 si ACCOUNT_STATUS contient "Closed", sinon 0`

```sql
SELECT AVG(CHURN::float) AS taux_churn_compte
FROM fact_compte_client;
```

### 1.2 Taux de churn client complet (Full Churn)
Proportion de clients dont **tous** les comptes sont clôturés (churn total,
plus révélateur qu'un churn partiel d'un client multi-comptes).

**Formule métier** : `CLIENT_FULL_CHURN = 1 si NB_COMPTES_CLOS = NB_COMPTES`

```sql
SELECT AVG(CLIENT_FULL_CHURN::float) AS taux_churn_client_complet
FROM (SELECT DISTINCT CUSTOMER_NO, CLIENT_FULL_CHURN FROM fact_compte_client) c;
```

### 1.3 Taux de churn par segment
Décliner le taux de churn (KPI 1.1) par dimension d'analyse.

```sql
-- Par branche
SELECT BRANCH, AVG(CHURN::float) AS taux_churn
FROM fact_compte_client
GROUP BY BRANCH
ORDER BY taux_churn DESC;

-- Par secteur d'activité (industrie)
SELECT di.INDUSTRY_LABEL, AVG(f.CHURN::float) AS taux_churn
FROM fact_compte_client f
JOIN dim_industry di ON f.INDUSTRY_SK = di.INDUSTRY_SK
GROUP BY di.INDUSTRY_LABEL
ORDER BY taux_churn DESC;

-- Par catégorie de compte / produit
SELECT ACCOUNT_CATEGORY, PRODUCT_LINE, AVG(CHURN::float) AS taux_churn
FROM fact_compte_client
GROUP BY ACCOUNT_CATEGORY, PRODUCT_LINE
ORDER BY taux_churn DESC;
```

### 1.4 Répartition des motifs de clôture
Distribution des `CLOSURE_REASON` parmi les comptes churnés (inclut le code
dédié `UNKNOWN` = motif non renseigné, distinct de "Autre").

```sql
SELECT dc.CLOSURE_REASON_LABEL, COUNT(*) AS nb_comptes,
       COUNT(*) * 100.0 / SUM(COUNT(*)) OVER () AS pct
FROM fact_compte_client f
JOIN dim_closure_reason dc ON f.CLOSURE_REASON_SK = dc.CLOSURE_REASON_SK
WHERE f.CHURN = 1
GROUP BY dc.CLOSURE_REASON_LABEL
ORDER BY nb_comptes DESC;
```

---

## 2. KPIs de portefeuille client

### 2.1 Nombre total de clients / comptes actifs
```sql
SELECT COUNT(DISTINCT CUSTOMER_NO) AS nb_clients,
       COUNT(DISTINCT ACCOUNT_NO)  AS nb_comptes
FROM fact_compte_client
WHERE CHURN = 0;
```

### 2.2 Multi-bancarisation (comptes et produits distincts par client)
Moyenne de `NB_COMPTES` et `NB_PRODUITS_DISTINCTS` (indicateur d'engagement :
un client multi-produits est statistiquement moins volatil).

```sql
SELECT AVG(NB_COMPTES) AS moy_comptes_par_client,
       AVG(NB_PRODUITS_DISTINCTS) AS moy_produits_par_client
FROM (SELECT DISTINCT CUSTOMER_NO, NB_COMPTES, NB_PRODUITS_DISTINCTS FROM fact_compte_client) c;
```

### 2.3 Ancienneté moyenne (client / compte), churn vs actif
Compare l'ancienneté (en années) des clients/comptes churnés à celle des
actifs — un churn plus fréquent en début de relation signale un problème
d'onboarding.

```sql
SELECT CHURN,
       AVG(CLIENT_SENIORITY_YEARS)  AS anciennete_client_moy,
       AVG(ACCOUNT_SENIORITY_YEARS) AS anciennete_compte_moy
FROM fact_compte_client
GROUP BY CHURN;
```

### 2.4 Ancienneté de la dernière revue KYC (`DAYS_SINCE_LAST_REVIEW`)
Suivi de conformité : proportion de comptes dont la revue KYC date de plus
d'un an (365 jours), à croiser avec le taux de churn.

```sql
SELECT
    CASE WHEN DAYS_SINCE_LAST_REVIEW > 365 THEN 'Revue en retard' ELSE 'À jour' END AS statut_kyc,
    COUNT(*) AS nb_comptes,
    AVG(CHURN::float) AS taux_churn
FROM fact_compte_client
GROUP BY statut_kyc;
```

---

## 3. KPIs financiers

### 3.1 Solde moyen (`ACCT_BALANCE`), churn vs actif
```sql
SELECT CHURN, AVG(ACCT_BALANCE) AS solde_moyen, COUNT(*) AS nb_comptes
FROM fact_compte_client
GROUP BY CHURN;
```

### 3.2 Salaire moyen (`SALARY`) par tranche d'âge et churn
Segmentation démographique du churn.

```sql
SELECT
    CASE
        WHEN c.AGE < 30 THEN '< 30 ans'
        WHEN c.AGE < 45 THEN '30-44 ans'
        WHEN c.AGE < 60 THEN '45-59 ans'
        ELSE '60 ans et +'
    END AS tranche_age,
    AVG(f.SALARY) AS salaire_moyen,
    AVG(f.CHURN::float) AS taux_churn
FROM fact_compte_client f
JOIN dim_client c ON f.CLIENT_SK = c.CLIENT_SK
GROUP BY tranche_age
ORDER BY tranche_age;
```

### 3.3 Encours total par devise (`CURRENCY`)
```sql
SELECT dcur.CURRENCY_LABEL, SUM(f.ACCT_BALANCE) AS encours_total
FROM fact_compte_client f
JOIN dim_currency dcur ON f.CURRENCY_SK = dcur.CURRENCY_SK
WHERE f.CHURN = 0
GROUP BY dcur.CURRENCY_LABEL
ORDER BY encours_total DESC;
```

### 3.4 Taux fixe moyen (`FIXEDRATE`) par ligne de produit
```sql
SELECT PRODUCT_LINE, AVG(FIXEDRATE) AS taux_fixe_moyen
FROM fact_compte_client
WHERE FIXEDRATE > 0
GROUP BY PRODUCT_LINE
ORDER BY taux_fixe_moyen DESC;
```

---

## 4. KPIs de complétude / qualité de données (data quality)

### 4.1 Taux de dossiers complets (`COMPLETED_FILE`)
```sql
SELECT COMPLETED_FILE, COUNT(*) AS nb, COUNT(*) * 100.0 / SUM(COUNT(*)) OVER () AS pct
FROM dim_client
GROUP BY COMPLETED_FILE;
```

### 4.2 Incohérence de clôture (`FLAG_INCOHERENCE_CLOTURE`)
Comptes marqués fermés dans le SI mais présentant une incohérence détectée
en transformation (ex : motif de clôture manquant sur un compte fermé alors
qu'il devrait être renseigné).

```sql
SELECT FLAG_INCOHERENCE_CLOTURE, COUNT(*) AS nb_comptes
FROM fact_compte_client
GROUP BY FLAG_INCOHERENCE_CLOTURE;
```

---

## 5. Évolution temporelle (via `dim_date`)

### 5.1 Ouvertures / clôtures de comptes par mois
```sql
SELECT dd.YEAR, dd.MONTH, dd.MONTH_NAME,
       COUNT(*) FILTER (WHERE f.ACCT_CLOSE_DATE_SK = dd.DATE_SK) AS nb_clotures
FROM fact_compte_client f
JOIN dim_date dd ON f.ACCT_CLOSE_DATE_SK = dd.DATE_SK
GROUP BY dd.YEAR, dd.MONTH, dd.MONTH_NAME
ORDER BY dd.YEAR, dd.MONTH;
```

### 5.2 Taux de churn par cohorte d'ouverture (année d'ouverture de compte)
Identifie si les clients ouverts certaines années churnent davantage
(effet cohorte, ex. changement de politique commerciale).

```sql
SELECT dd.YEAR AS annee_ouverture, AVG(f.CHURN::float) AS taux_churn
FROM fact_compte_client f
JOIN dim_date dd ON f.ACCT_OPENING_DATE_SK = dd.DATE_SK
GROUP BY dd.YEAR
ORDER BY dd.YEAR;
```

---

## Notes d'usage

- Les KPIs des sections 1 à 5 sont pensés pour le reporting BI (dashboards).
- `CHURN` et `CLIENT_FULL_CHURN` sont aussi les variables cibles utilisées
  côté modélisation ML (composant supervisé du projet) : les mêmes colonnes
  servent donc à la fois au reporting et à l'entraînement du modèle.
- Les jointures dimensionnelles (`_SK`) supposent que `load_warehouse.py`
  a bien chargé les tables dans l'ordre dimensions -> fait (voir
  `load/load_warehouse.py`, `TABLE_LOAD_ORDER`).
