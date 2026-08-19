-- 001_init.sql
-- Financial Intelligence & Deal Analytics Platform — schéma initial (12 tables)
-- Justification complète de chaque choix de modélisation : docs/01_data_model.md
-- Toute la logique financière dérivée (ratios, EV, multiples) vit dans des vues
-- (sql/views/), jamais dans des colonnes stockées de ce fichier.

BEGIN;

-- ============================================================================
-- 1. sectors — taxonomie sectorielle, pour comparaison intra-secteur
-- ============================================================================
CREATE TABLE sectors (
    sector_id       SERIAL PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    sic_code        TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================================
-- 2. companies — référentiel entreprises (publiques et privées)
-- ============================================================================
CREATE TABLE companies (
    company_id      SERIAL PRIMARY KEY,
    cik             TEXT UNIQUE,              -- SEC EDGAR CIK, NULL si jamais filante
    ticker          TEXT UNIQUE,              -- NULL si privée / jamais cotée
    name            TEXT NOT NULL,
    sector_id       INTEGER REFERENCES sectors(sector_id),
    country         TEXT NOT NULL DEFAULT 'US',
    is_public       BOOLEAN NOT NULL DEFAULT TRUE,
    listed_exchange TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_companies_public_ticker
        CHECK (is_public = FALSE OR ticker IS NOT NULL)
);

CREATE INDEX idx_companies_sector ON companies(sector_id);

-- ============================================================================
-- 3. fiscal_periods — référentiel des périodes comptables (1 filing = 1 ligne)
-- ============================================================================
CREATE TABLE fiscal_periods (
    fiscal_period_id        SERIAL PRIMARY KEY,
    company_id               INTEGER NOT NULL REFERENCES companies(company_id),
    period_end_date          DATE NOT NULL,
    fiscal_year              INTEGER NOT NULL,
    period_type              TEXT NOT NULL CHECK (period_type IN ('FY','Q1','Q2','Q3','Q4')),
    form_type                TEXT CHECK (form_type IN ('10-K','10-Q','OTHER')),
    filing_date              DATE,
    source_accession_number  TEXT,             -- SEC accession number, traçabilité
    created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_fiscal_periods UNIQUE (company_id, period_end_date, period_type)
);

CREATE INDEX idx_fiscal_periods_company ON fiscal_periods(company_id);
CREATE INDEX idx_fiscal_periods_year ON fiscal_periods(fiscal_year);

-- ============================================================================
-- 4. income_statements — compte de résultat (1:1 avec fiscal_periods)
-- ============================================================================
CREATE TABLE income_statements (
    fiscal_period_id INTEGER PRIMARY KEY REFERENCES fiscal_periods(fiscal_period_id),
    revenue           NUMERIC,
    cogs              NUMERIC,
    gross_profit      NUMERIC,
    sga_expense       NUMERIC,
    ebitda            NUMERIC,
    ebit              NUMERIC,
    interest_expense  NUMERIC,
    pretax_income     NUMERIC,
    tax_expense       NUMERIC,
    net_income        NUMERIC,
    eps_basic         NUMERIC,
    eps_diluted       NUMERIC,
    shares_basic      NUMERIC,
    shares_diluted    NUMERIC
);

-- ============================================================================
-- 5. balance_sheets — bilan (1:1 avec fiscal_periods)
-- ============================================================================
CREATE TABLE balance_sheets (
    fiscal_period_id            INTEGER PRIMARY KEY REFERENCES fiscal_periods(fiscal_period_id),
    cash_and_equivalents        NUMERIC,
    total_current_assets        NUMERIC,
    total_assets                 NUMERIC,
    short_term_debt              NUMERIC,
    long_term_debt               NUMERIC,
    total_current_liabilities    NUMERIC,
    total_liabilities            NUMERIC,
    total_equity                 NUMERIC
);

-- ============================================================================
-- 6. cash_flow_statements — flux de trésorerie (1:1 avec fiscal_periods)
-- ============================================================================
CREATE TABLE cash_flow_statements (
    fiscal_period_id INTEGER PRIMARY KEY REFERENCES fiscal_periods(fiscal_period_id),
    cfo               NUMERIC,   -- cash flow from operations
    capex             NUMERIC,
    cfi               NUMERIC,   -- cash flow from investing
    cff               NUMERIC,   -- cash flow from financing
    dividends_paid    NUMERIC
);

-- ============================================================================
-- 7. market_prices — cours, volume, capitalisation quotidiens
-- ============================================================================
CREATE TABLE market_prices (
    market_price_id     BIGSERIAL PRIMARY KEY,
    company_id          INTEGER NOT NULL REFERENCES companies(company_id),
    price_date          DATE NOT NULL,
    close_price         NUMERIC NOT NULL,
    volume              BIGINT,
    shares_outstanding  NUMERIC,
    market_cap          NUMERIC,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_market_prices UNIQUE (company_id, price_date)
);

CREATE INDEX idx_market_prices_company_date ON market_prices(company_id, price_date);

-- ============================================================================
-- 8. macro_indicators — séries macro FRED (taux, spreads)
-- ============================================================================
CREATE TABLE macro_indicators (
    macro_indicator_id  BIGSERIAL PRIMARY KEY,
    series_code         TEXT NOT NULL,   -- ex. 'DGS10', 'BAMLH0A0HYM2'
    obs_date            DATE NOT NULL,
    value               NUMERIC,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_macro_indicators UNIQUE (series_code, obs_date)
);

CREATE INDEX idx_macro_indicators_series_date ON macro_indicators(series_code, obs_date);

-- ============================================================================
-- 9. transactions — transactions M&A (annonces publiques, traçabilité obligatoire)
-- ============================================================================
CREATE TABLE transactions (
    transaction_id         SERIAL PRIMARY KEY,
    acquirer_company_id    INTEGER REFERENCES companies(company_id),
    target_company_id      INTEGER REFERENCES companies(company_id),
    announce_date           DATE NOT NULL,
    close_date              DATE,
    status                  TEXT NOT NULL CHECK (status IN ('announced','completed','terminated')),
    payment_type            TEXT CHECK (payment_type IN ('cash','stock','mixed','other')),
    offer_price_per_share   NUMERIC,
    deal_value              NUMERIC,
    unaffected_price        NUMERIC,
    unaffected_price_date   DATE,
    source_type             TEXT NOT NULL CHECK (source_type IN ('8-K','press_release','other')),
    source_url              TEXT NOT NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_transactions_parties CHECK (acquirer_company_id IS DISTINCT FROM target_company_id)
);

CREATE INDEX idx_transactions_target ON transactions(target_company_id);
CREATE INDEX idx_transactions_acquirer ON transactions(acquirer_company_id);
CREATE INDEX idx_transactions_announce_date ON transactions(announce_date);

-- ============================================================================
-- 10. transaction_financials — financials de la cible au moment de l'annonce
-- ============================================================================
CREATE TABLE transaction_financials (
    transaction_id       INTEGER PRIMARY KEY REFERENCES transactions(transaction_id),
    target_revenue_ttm   NUMERIC,
    target_ebitda_ttm    NUMERIC,
    target_net_debt      NUMERIC,
    ev_at_offer          NUMERIC,
    ev_ebitda_multiple   NUMERIC,
    notes                TEXT
);

-- ============================================================================
-- 11. screening_profiles — métadonnées des profils de screening PE
-- ============================================================================
CREATE TABLE screening_profiles (
    screening_profile_id   SERIAL PRIMARY KEY,
    code                    TEXT NOT NULL UNIQUE CHECK (code IN ('pe_growth','pe_value','quality','distressed')),
    name                    TEXT NOT NULL,
    description             TEXT,
    config_path             TEXT NOT NULL,   -- ex. 'configs/screening/pe_growth.yaml'
    config_version          TEXT NOT NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================================
-- 12. screening_results — audit trail des exécutions du moteur de screening
-- ============================================================================
CREATE TABLE screening_results (
    screening_result_id    BIGSERIAL PRIMARY KEY,
    screening_profile_id   INTEGER NOT NULL REFERENCES screening_profiles(screening_profile_id),
    company_id              INTEGER NOT NULL REFERENCES companies(company_id),
    fiscal_period_id        INTEGER NOT NULL REFERENCES fiscal_periods(fiscal_period_id),
    run_date                 TIMESTAMPTZ NOT NULL DEFAULT now(),
    passed                   BOOLEAN NOT NULL,
    score                    NUMERIC,
    config_hash              TEXT NOT NULL,
    CONSTRAINT uq_screening_results UNIQUE (screening_profile_id, company_id, fiscal_period_id, run_date)
);

CREATE INDEX idx_screening_results_profile ON screening_results(screening_profile_id);
CREATE INDEX idx_screening_results_company ON screening_results(company_id);

COMMIT;
