# 02 — Data Warehouse

Modèle dimensionnel et entrepôt de données du Projet Intégré (Churn Client).

## Structure

```
02_data_warehouse/
├── schema/
│   ├── create_tables.sql   # DDL : fact_compte_client + dimensions (PK/FK, types)
│   └── star_schema.png     # Diagramme du modèle en étoile
├── load/
│   └── load_warehouse.py   # Applique le schéma puis charge les données dans PostgreSQL
├── kpis.md                 # Liste des KPIs et formules (SQL) associées
└── README.md
```

## Modèle en étoile

- **Table de faits** : `fact_compte_client` (grain : un compte-produit)
  contient les mesures (`ACCT_BALANCE`, `SALARY`, `AMOUNT`, `FIXEDRATE`,
  `AGE`, anciennetés...) et la variable cible `CHURN` / `CLIENT_FULL_CHURN`.
- **Dimensions** : `dim_client`, `dim_date`, `dim_account_category`,
  `dim_currency`, `dim_closure_reason`, `dim_industry`, chacune dotée d'une
  surrogate key (`_SK`) pour des jointures stables et efficaces.

Le fait et les dimensions sont produits par le pipeline ETL (`01_etl/`) :
`transform.py` calcule les features et le fait enrichi, `load.py` (dans
`01_etl/src/`) le découpe en tables du schéma en étoile
(`build_star_schema_tables`).

## Utilisation

1. **Créer/mettre à jour le schéma et charger les données :**

   ```bash
   python 02_data_warehouse/load/load_warehouse.py
   ```

   Options utiles :
   - `--sample 5000` : test rapide sur un échantillon (au lieu des 528 883 lignes)
   - `--skip-schema` : recharger les données sans ré-exécuter `create_tables.sql`

2. **Prérequis** : PostgreSQL accessible (variables d'environnement `PGHOST`,
   `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD` — valeurs par défaut pour un
   PostgreSQL local dans `load_warehouse.py`), et données brutes disponibles
   via Git LFS (`git lfs pull`, voir `data/README.md`).

3. **KPIs** : voir `kpis.md` pour la liste des indicateurs (taux de churn
   global/complet, segmentation par branche/industrie/produit, motifs de
   clôture, ancienneté, indicateurs financiers) avec leur requête SQL.

## Notes

- `create_tables.sql` doit rester idempotent (`CREATE TABLE IF NOT EXISTS`)
  pour pouvoir être relancé sans erreur à chaque exécution de
  `load_warehouse.py`.
- `load_warehouse.py` fait un `TRUNCATE ... CASCADE` + rechargement complet à
  chaque exécution (pas de chargement incrémental pour l'instant).