-- `SELECT * FROM v_company_financial_profile WHERE ticker = 'AAPL'` prenait
-- 332,75 ms pour 19 lignes sur 714. EXPLAIN ANALYZE : les 5 vues empilées
-- recalculent LAG() PARTITION BY company_id sur les 714 lignes avant que le
-- filtre `ticker` ne s'applique — le planificateur ne peut pas pousser un
-- filtre à travers une partition de fonction fenêtrée sur une autre colonne.
--
-- Matérialisation : v_sector_rankings/v_trailing_trends/v_screening_base
-- sont redéfinies sur la version matérialisée. Rafraîchie après chaque
-- chargement (load_to_postgres.py). Détail complet, avant/après :
-- sql/optimization/README.md.

BEGIN;

CREATE MATERIALIZED VIEW mv_company_financial_profile AS
SELECT * FROM v_company_financial_profile;

-- Index unique requis pour permettre REFRESH MATERIALIZED VIEW CONCURRENTLY
-- (rafraîchissement sans verrou bloquant les lectures en cours).
CREATE UNIQUE INDEX idx_mv_cfp_fiscal_period ON mv_company_financial_profile (fiscal_period_id);

-- Index ciblés : historique d'une entreprise, classement sectoriel par exercice.
CREATE INDEX idx_mv_cfp_ticker_year ON mv_company_financial_profile (ticker, fiscal_year);
CREATE INDEX idx_mv_cfp_sector_year ON mv_company_financial_profile (sector_id, fiscal_year);

COMMIT;
