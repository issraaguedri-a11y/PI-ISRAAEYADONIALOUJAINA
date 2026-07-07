-- ============================================================================
-- create_tables.sql
-- ----------------------------------------------------------------------------
-- Modèle en étoile du data warehouse "Churn Client" (base PostgreSQL churn_dw).
--
-- 1 table de faits (fact_compte_client, grain = ligne compte-produit) reliée
-- à 6 tables de dimensions par des surrogate keys entières (suffixe _SK).
-- Voir schema/star_schema.png pour le schéma visuel et kpis.md pour les
-- indicateurs calculés à partir de ce modèle.
--
-- Ordre d'exécution : les dimensions sont créées avant le fait (contraintes
-- de clé étrangère). Utiliser DROP ... CASCADE pour repartir de zéro.
--
-- Usage :
--   psql -h $PGHOST -U $PGUSER -d $PGDATABASE -f create_tables.sql
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Nettoyage (repartir d'un schéma propre)
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS fact_compte_client CASCADE;
DROP TABLE IF EXISTS dim_client CASCADE;
DROP TABLE IF EXISTS dim_closure_reason CASCADE;
DROP TABLE IF EXISTS dim_account_category CASCADE;
DROP TABLE IF EXISTS dim_industry CASCADE;
DROP TABLE IF EXISTS dim_currency CASCADE;
DROP TABLE IF EXISTS dim_date CASCADE;

-- ----------------------------------------------------------------------------
-- DIM_CLIENT : un enregistrement par client (CUSTOMER_NO)
-- ----------------------------------------------------------------------------
CREATE TABLE dim_client (
    client_sk        INTEGER PRIMARY KEY,
    customer_no      VARCHAR(20)  NOT NULL UNIQUE,
    nationality      VARCHAR(10),
    residence        VARCHAR(10),
    marital_status   VARCHAR(30),   -- 'Non applicable' pour les personnes morales
    birth_year       SMALLINT,
    age              SMALLINT,      -- plafonné à 100, imputé par le mode si manquant
    nature_client    VARCHAR(10),   -- PPH, PM (personne morale), PRO, ...
    partyclass       VARCHAR(20),
    lob              VARCHAR(10),
    score_kyc        VARCHAR(10),
    completed_file   VARCHAR(10)    -- 'YES' / 'Non'
);

COMMENT ON TABLE dim_client IS 'Dimension client : attributs démographiques et KYC, un enregistrement par CUSTOMER_NO.';

-- ----------------------------------------------------------------------------
-- DIM_CLOSURE_REASON : motifs de clôture de compte
-- ----------------------------------------------------------------------------
CREATE TABLE dim_closure_reason (
    closure_reason_sk     INTEGER PRIMARY KEY,
    closure_reason         VARCHAR(30) NOT NULL UNIQUE,  -- ex: 'BANK.REASON.13', 'UNKNOWN'
    closure_reason_label   VARCHAR(150)
);

COMMENT ON TABLE dim_closure_reason IS 'Motifs de clôture de compte. Le code UNKNOWN / libellé "Non renseigné" désigne les comptes clôturés sans motif renseigné dans le SI source ; il est volontairement distinct du motif réel "Autre" pour ne pas biaiser la distribution.';

-- ----------------------------------------------------------------------------
-- DIM_ACCOUNT_CATEGORY : catégories de compte/produit
-- ----------------------------------------------------------------------------
CREATE TABLE dim_account_category (
    account_category_sk    INTEGER PRIMARY KEY,
    account_category        VARCHAR(20) NOT NULL UNIQUE,
    account_category_label  VARCHAR(150)  -- 'Non disponible' si absente côté source
);

COMMENT ON TABLE dim_account_category IS 'Catégories de compte (codes numériques ATB/BANK).';

-- ----------------------------------------------------------------------------
-- DIM_INDUSTRY : secteur d'activité du client
-- ----------------------------------------------------------------------------
CREATE TABLE dim_industry (
    industry_sk     INTEGER PRIMARY KEY,
    industry         VARCHAR(20) NOT NULL UNIQUE,
    industry_label   VARCHAR(150)
);

COMMENT ON TABLE dim_industry IS 'Secteurs d''activité (nomenclature interne).';

-- ----------------------------------------------------------------------------
-- DIM_CURRENCY : devises
-- ----------------------------------------------------------------------------
CREATE TABLE dim_currency (
    currency_sk     INTEGER PRIMARY KEY,
    currency         VARCHAR(5) NOT NULL UNIQUE,   -- ex: 'TND', 'EUR', 'USD'
    currency_label   VARCHAR(100)
);

COMMENT ON TABLE dim_currency IS 'Devises des comptes/produits.';

-- ----------------------------------------------------------------------------
-- DIM_DATE : dimension calendaire (une ligne par date distincte du fait)
-- ----------------------------------------------------------------------------
CREATE TABLE dim_date (
    date_sk         INTEGER PRIMARY KEY,     -- format YYYYMMDD
    date_value      DATE NOT NULL UNIQUE,
    year             SMALLINT NOT NULL,
    quarter          SMALLINT NOT NULL,
    month            SMALLINT NOT NULL,
    month_name       VARCHAR(15) NOT NULL,
    day              SMALLINT NOT NULL,
    day_of_week      SMALLINT NOT NULL,        -- 0 = lundi
    day_name         VARCHAR(10) NOT NULL,
    week_of_year     SMALLINT NOT NULL,
    is_weekend       BOOLEAN NOT NULL,
    is_month_end     BOOLEAN NOT NULL,
    is_year_end      BOOLEAN NOT NULL
);

COMMENT ON TABLE dim_date IS 'Dimension calendaire couvrant toutes les dates >= 1900-01-01 rencontrées dans le fait (ouverture client/compte, clôture...).';

-- ----------------------------------------------------------------------------
-- FACT_COMPTE_CLIENT : grain = 1 ligne par couple (compte, produit)
-- ----------------------------------------------------------------------------
CREATE TABLE fact_compte_client (
    -- Clés naturelles (traçabilité / lisibilité)
    customer_no                 VARCHAR(20)  NOT NULL,
    account_no                  VARCHAR(20)  NOT NULL,
    branch                      VARCHAR(10),
    account_status              VARCHAR(20),

    -- Variables cibles / indicateurs de churn
    churn                       SMALLINT NOT NULL,          -- 1 si ce compte est clôturé
    client_full_churn           SMALLINT NOT NULL,          -- 1 si TOUS les comptes du client sont clôturés

    -- Mesures financières (valeurs manquantes imputées par le mode, voir kpis.md / README)
    acct_balance                NUMERIC(18,3),
    salary                      NUMERIC(18,3),
    amount                      NUMERIC(18,3),
    fixedrate                   NUMERIC(6,3),               -- 0 = compte non rémunéré (courant)

    -- Variables démographiques / d'ancienneté dérivées
    age                         SMALLINT,
    client_seniority_years      NUMERIC(8,3),
    account_seniority_years     NUMERIC(8,3),
    days_since_last_review      NUMERIC(10,1),

    -- Agrégats comportementaux au niveau client
    nb_comptes                  INTEGER NOT NULL,
    nb_produits_distincts       INTEGER NOT NULL,
    nb_comptes_clos             INTEGER NOT NULL,
    flag_incoherence_cloture    BOOLEAN NOT NULL,

    -- Codes métier bruts (conservés pour lisibilité, en plus des _SK ci-dessous)
    account_category             VARCHAR(20),
    currency                     VARCHAR(5),
    closure_reason                VARCHAR(30),
    industry                      VARCHAR(20),
    product_group                 VARCHAR(50),
    product_line                  VARCHAR(50),
    product                        VARCHAR(100),

    -- Dates brutes
    cust_opening_date            DATE,
    acct_opening_date            DATE,
    acct_close_date              DATE,

    -- Surrogate keys (clés étrangères vers les dimensions)
    client_sk                    INTEGER NOT NULL REFERENCES dim_client(client_sk),
    closure_reason_sk             INTEGER REFERENCES dim_closure_reason(closure_reason_sk),
    account_category_sk           INTEGER REFERENCES dim_account_category(account_category_sk),
    industry_sk                   INTEGER REFERENCES dim_industry(industry_sk),
    currency_sk                   INTEGER REFERENCES dim_currency(currency_sk),
    cust_opening_date_sk          INTEGER REFERENCES dim_date(date_sk),
    acct_opening_date_sk          INTEGER REFERENCES dim_date(date_sk),
    acct_close_date_sk            INTEGER REFERENCES dim_date(date_sk)
);

COMMENT ON TABLE fact_compte_client IS 'Table de faits, grain = 1 ligne par couple (compte, produit). CHURN = compte clôturé ; CLIENT_FULL_CHURN = tous les comptes du client sont clôturés.';

-- Les _SK peuvent être NULL quand le code métier correspondant est absent
-- côté source (ex : pas de catégorie de compte renseignée) -> traité comme
-- "non applicable", pas comme une valeur par défaut arbitraire.

-- ----------------------------------------------------------------------------
-- Index (accélèrent les jointures et les agrégations de kpis.md)
-- ----------------------------------------------------------------------------
CREATE INDEX idx_fact_customer_no        ON fact_compte_client (customer_no);
CREATE INDEX idx_fact_account_no         ON fact_compte_client (account_no);
CREATE INDEX idx_fact_churn              ON fact_compte_client (churn);
CREATE INDEX idx_fact_client_sk          ON fact_compte_client (client_sk);
CREATE INDEX idx_fact_closure_reason_sk  ON fact_compte_client (closure_reason_sk);
CREATE INDEX idx_fact_account_category_sk ON fact_compte_client (account_category_sk);
CREATE INDEX idx_fact_industry_sk        ON fact_compte_client (industry_sk);
CREATE INDEX idx_fact_currency_sk        ON fact_compte_client (currency_sk);
CREATE INDEX idx_fact_acct_close_date_sk ON fact_compte_client (acct_close_date_sk);